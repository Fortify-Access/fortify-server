import asyncio
import pytz
import dpkt
import subprocess
from datetime import datetime
from sqlmodel import Session, select
from scapy.all import AsyncSniffer, TCP, IP
from api import models, extentions

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

async def check_online_clients():
    def packet_callback(packet):
        if extentions.redis_client.sismember('active_ports', packet[TCP].sport):
            port = packet[TCP].sport
            client_ip = packet[IP].dst

        elif extentions.redis_client.sismember('active_ports', packet[TCP].dport):
            port = packet[TCP].dport
            client_ip = packet[IP].src

        else:
            return

        if not extentions.redis_client.sismember(f"online_{port}", client_ip):
            extentions.redis_client.sadd(f"online_{port}", client_ip)
            extentions.redis_client.expire(f"online_{port}", 30, nx=True)

    sniffer = AsyncSniffer(filter="tcp", prn=packet_callback, store=0)
    sniffer.start()

async def analyze_packets():
    with open('/var/log/tcpdump/packets.pcap', 'rb') as packets_file:
        pcap = dpkt.pcap.Reader(packets_file)
        for timestamp, packet in pcap:
            eth = dpkt.ethernet.Ethernet(packet)
            if isinstance(eth.data, dpkt.ip.IP):
                yield eth.data.data.sport, eth.data.data.dport, len(packet)

async def traffic_usage_handler(period: int):
    while True:
        await asyncio.sleep(period)
        for src_port, dst_port, packet_length in analyze_packets():
            if extentions.redis_client.sismember('active_ports', src_port):
                download = int(extentions.redis_client.get(f"download_{src_port}") or 0)
                download += packet_length
                extentions.redis_client.set(f"download_{src_port}", download)
                print(download)

            elif extentions.redis_client.sismember('active_ports', dst_port):
                upload = int(extentions.redis_client.get(f"upload_{dst_port}") or 0)
                upload += packet_length
                extentions.redis_client.set(f"upload_{dst_port}", upload)
                print(upload)

            else:
                continue
        subprocess.run(["truncate", "-s", "0", "/var/log/tcpdump/packets.pcap"])

async def commit_traffic_usages_to_db(period: int):
    while True:
        await asyncio.sleep(period)
        with Session(extentions.engine) as session:
            for port in extentions.redis_client.smembers('active_ports'):
                port = int(port)
                upload = int(extentions.redis_client.get(f"upload_{port}") or 0)
                download = int(extentions.redis_client.get(f"download_{port}") or 0)
                query = select(models.InboundModel).where(models.InboundModel.listen_port == port)
                inbound = session.exec(query).first()
                if inbound:
                    inbound.upload = upload
                    inbound.download = download
                    inbound.traffic_usage = upload + download
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
