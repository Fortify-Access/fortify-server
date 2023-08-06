from starlette.responses import JSONResponse
from sqlmodel import Session, select
from api.extentions import engine
from api import models, extentions

async def inbound_list(request):
    with Session(engine) as session:
        try:
            query = select(models.InboundModel)
            results = session.exec(query).all()
            return JSONResponse({"success": True, "inbounds": [result.to_completed_json() for result in results]})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

async def inbound_get_last_updates(request):
    with Session(engine) as session:
        try:
            query = select(models.InboundModel)
            results = session.exec(query).all()
            return JSONResponse({"success": True, "inbounds": [result.dict(include={'tag', 'upload', 'download', 'traffic_usage', 'is_active'}) | {
                'online_clients': [str(ip) for ip in extentions.redis_client.smembers(f"online_{result.listen_port}")]
            } for result in results]})

        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

async def inbound_create(request):
    with Session(engine) as session:
        try:
            data = await request.json()
            inbound = models.InboundModel(**data["inbound"])
            inbound.tls = models.TlsModel(**data["tls"])
            inbound.users = [models.UserModel(**user) for user in data["users"]]
            session.add(inbound)
            session.add(inbound.tls)
            session.add_all(inbound.users)
            session.commit()
            session.refresh(inbound)
            extentions.import_inbound(inbound.to_singbox_dict())
            extentions.redis_client.sadd('active_ports', inbound.listen_port)
            extentions.realod_singbox()
            return JSONResponse({"success": True, "inbound": inbound.to_completed_json()})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

async def inbound_delete(request):
    with Session(engine) as session:
        try:
            if tag := request.query_params.get('tag', None):
                query = select(models.InboundModel).where(models.InboundModel.tag == tag)
                inbound = session.exec(query).first()
            elif port := request.query_params.get('port', None):
                query = select(models.InboundModel).where(models.InboundModel.port == port)
                inbound = session.exec(query).first()
            else:
                return JSONResponse({"success": False, "error": "To delete an inband, you must provide its port or tag"}, status_code=404)

            session.delete(inbound)
            session.commit()
            extentions.export_inbound(inbound.tag)
            extentions.redis_client.srem('active_ports', inbound.listen_port)
            extentions.redis_client.delete(inbound.listen_port)
            extentions.realod_singbox()
            return JSONResponse({"success": True, "inbound": inbound.to_completed_json()})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

async def inbound_get(request):
    with Session(engine) as session:
        try:
            if tag := request.query_params.get('tag', None):
                query = select(models.InboundModel).where(models.InboundModel.tag == tag)
                inbound = session.exec(query).first()
            elif port := request.query_params.get('port', None):
                query = select(models.InboundModel).where(models.InboundModel.listen_port == port)
                inbound = session.exec(query).first()
            else:
                return JSONResponse({"success": False, "error": "To get the information of an inband, you must provide its port or tag"}, status_code=404)
            return JSONResponse({"success": True, "inbound": inbound.to_completed_json()})

        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

async def inbound_update(request):
    with Session(engine) as session:
        try:
            if tag := request.query_params.get('tag', None):
                query = select(models.InboundModel).where(models.InboundModel.tag == tag)
                inbound = session.exec(query).first()
            elif port := request.query_params.get('port', None):
                query = select(models.InboundModel).where(models.InboundModel.listen_port == port)
                inbound = session.exec(query).first()
            else:
                return JSONResponse({"success": False, "error": "To update the information of an inband, you must provide its port or tag"}, status_code=404)

            updated_fields = request.json()
            old_inbound = inbound

            if "id" or "traffic_usage" or "creation_date" in updated_fields["inbound"].keys():
                return JSONResponse({"success": False, "error": "You can not change this information of an inbound."}, status_code=402)
            # Update inbound attrs
            for key, value in updated_fields["inbound"].items():
                setattr(inbound, key, value)
            # Update Tls attrs
            for key, value in updated_fields["tls"].items():
                setattr(inbound.tls, key.value)

            session.add(inbound)
            session.add(inbound.tls)
            session.commit()
            session.refresh(inbound)
            extentions.export_inbound(old_inbound.tag)
            extentions.redis_client.srem('active_ports', old_inbound.listen_port)

            if "port" in updated_fields["inbound"].keys():
                extentions.redis_client.set(f"upload_{inbound.listen_port}", int(extentions.redis_client.get(f"upload_{old_inbound.port}")))
                extentions.redis_client.set(f"download_{inbound.listen_port}", int(extentions.redis_client.get(f"download_{old_inbound.port}")))
                extentions.redis_client.delete(f"upload_{old_inbound.listen_port}")
                extentions.redis_client.delete(f"download_{old_inbound.listen_port}")

            if "is_active" in updated_fields["inbound"].keys():
                if not (old_inbound.is_active == True and inbound.is_active == False):
                    extentions.import_inbound(inbound.to_singbox_dict())
                    extentions.redis_client.sadd('active_ports', inbound.listen_port)

            extentions.realod_singbox()
            return JSONResponse({"success": True, "inbound": inbound.to_completed_json()})

        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)
