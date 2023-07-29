import asyncio
import pytz
from datetime import datetime
from sqlmodel import Session, select
from scapy.all import AsyncSniffer, TCP
from api import models
from api import extentions

async def check_expirations(period: int):
    while True:
        with Session(extentions.engine) as session:
            query = select(models.InboundModel).where(models.InboundModel.expiration_date < datetime.now(pytz.timezone('Asia/Tehran')))
            expired_inbounds = session.exec(query).all()
            for inbound in expired_inbounds:
                extentions.export_inbound(inbound.tag)
                inbound.is_active = False
                extentions.redis_client.srem('active_ports', inbound.listen_port)
            session.add_all(expired_inbounds)
            session.commit()
        await asyncio.sleep(period)

async def check_reached_traffic_limitaion(period: int):
    while True:
        with Session(extentions.engine) as session:
            query = select(models.InboundModel).where(models.InboundModel.traffic_usage > models.InboundModel.traffic_limitation)
            expired_inbounds = session.exec(query).all()
            for inbound in expired_inbounds:
                extentions.export_inbound(inbound.tag)
                inbound.is_active = False
                extentions.redis_client.srem('active_ports', inbound.listen_port)
            session.add_all(expired_inbounds)
            session.commit()
        await asyncio.sleep(period)

async def check_traffic_usages():
    def packet_callback(packet):
        if extentions.redis_client.sismember('active_ports', packet[TCP].sport):
            port = packet[TCP].sport
        elif extentions.redis_client.sismember('active_ports', packet[TCP].dport):
            port = packet[TCP].dport
        else:
            return

        usage = int(extentions.redis_client.get(port) or 0)
        usage += len(packet)
        extentions.redis_client.set(port, usage)

    sniffer = AsyncSniffer(filter="tcp", prn=packet_callback)
    sniffer.start()

async def commit_traffic_usages_to_db(period: int):
    while True:
        await asyncio.sleep(period)
        for port in extentions.redis_client.smembers('active_ports'):
            port = int(port)
            usage = int(extentions.redis_client.get(port) or 0)
            with Session(extentions.engine) as session:
                query = select(models.InboundModel).where(models.InboundModel.listen_port == port)
                inbound = session.exec(query).first()
                if inbound:
                    inbound.traffic_usage = usage
                    print(inbound.traffic_usage)
                    session.add(inbound)
                    session.commit()
                    continue
                extentions.redis_client.srem('active_ports', port)

async def project_initializer():
    # Syncing the ports in redis and sqlite
    with Session(extentions.engine) as session:
        query = select(models.InboundModel)
        inbounds = session.exec(query).all()
        inbounds_port = extentions.redis_client.smembers('active_ports')

        for inbound in inbounds:
            if inbound.listen_port not in inbounds_port:
                extentions.redis_client.sadd('active_ports', inbound.listen_port)
                inbounds_port.remove(inbound.listen_port)

        extentions.redis_client.srem('active_ports', inbounds_port)
