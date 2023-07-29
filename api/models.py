from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
import pytz
import json


class InboundModel(SQLModel, table=True):
    id: int = Field(primary_key=True)
    tag: str = Field(unique=True)
    type: str
    listen: str
    listen_port: int = Field(unique=True)
    tcp_fast_open: bool
    udp_fragment: bool
    sniff: bool
    sniff_override_destination: bool
    sniff_timeout: Optional[int] = Field(nullable=True)
    domain_strategy: Optional[str] = Field(default='ipv4_only')
    udp_timeout: Optional[int] = Field(nullable=True)
    proxy_protocol: bool
    proxy_protocol_accept_no_header: bool
    users: List["UserModel"] = Relationship(sa_relationship_kwargs={"cascade": "delete"})
    tls: Optional["TlsModel"] = Relationship(sa_relationship_kwargs={"cascade": "delete", "uselist": False})

    traffic_usage: int = Field(default=0)
    traffic_limitation: Optional[int] = Field(nullable=True)
    expiration_date: Optional[datetime] = Field(nullable=True)
    creation_date: datetime = Field(default_factory=lambda: datetime.now(pytz.timezone('Asia/Tehran')))
    is_active: bool = Field(default=True)

    def to_completed_json(self):
        data = json.loads(self.json())
        data["users"] = [user.dict() for user in self.users]
        data["tls"] = self.tls.dict()
        return json.dumps(data)

    def to_singbox_dict(self):
        data = self.dict(exclude={'id', 'traffic_usage', 'traffic_limitation', 'creation_date', 'expiration_date', 'is_active'})
        data["users"] = [user.dict(exclude={'id', 'inbound_id'}) for user in self.users]
        data["tls"] = self.tls.dict(exclude={'id', 'inbound_id'})
        return data


class UserModel(SQLModel, table=True):
    id: int = Field(primary_key=True)
    name: Optional[str] = Field(nullable=True)
    uuid: str = Field(unique=True)
    flow: Optional[str] = Field(default='xtls-rprx-vision', nullable=True)

    inbound_id: Optional[int] = Field(foreign_key='inboundmodel.id', index=True)


class TlsModel(SQLModel, table=True):
    id: int = Field(primary_key=True)
    type: str = Field(default='reality')
    server_name: str = Field(default='discord.com')
    handshake_server: str = Field(default='discord.com')
    handshake_port: int = Field(default=443)
    private_key: str = Field(unique=True)
    short_id: str = Field(unique=True)

    inbound_id: Optional[int] = Field(foreign_key='inboundmodel.id', index=True)
