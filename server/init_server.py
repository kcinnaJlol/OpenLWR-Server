import uuid
from server.connection_manager import manager
from server.server_events import server_user_logout_event
from server.constants import packets
from server.helpers import packet_helper
from server.client_events import client_switch_parameters_update_event
from server.server_events import server_switch_parameters_update_event


def init_server(websocket):
    token_str = str(uuid.uuid4())
    token_object = manager.connect(websocket, token_str)

    # inform the client of all switch positions
    server_switch_parameters_update_event.fire_initial(token_str)

    try:
        for packet in websocket:
            print(packet) # TODO: proper logging system

            packet_id, packet_data = packet_helper.parse(packet)

            if packet_id == packets.ClientPackets.SWITCH_PARAMETERS_UPDATE:
                client_switch_parameters_update_event.handle(packet_data)

    except Exception:
        manager.disconnect(token_str)
        server_user_logout_event.fire(token_object.username)