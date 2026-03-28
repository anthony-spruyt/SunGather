import json
import logging
import time

import requests
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException
from websocket import create_connection

from version import __version__


class SungrowModbusWebClient(ModbusTcpClient):
    """Modbus over Sungrow HTTP client for WiNet-S Dongle."""

    # Parameters accepted by ModbusTcpClient.__init__
    _ACCEPTED_KWARGS = {
        'framer', 'port', 'name', 'source_address',
        'reconnect_delay', 'reconnect_delay_max', 'timeout',
        'retries', 'trace_packet', 'trace_pdu', 'trace_connect',
    }

    def __init__(self, host='127.0.0.1', port=8082, **kwargs):
        self.dev_host = host
        self.ws_port = port
        self.timeout = kwargs.get('timeout', '5')
        self.ws_socket = None

        # Filter to only params ModbusTcpClient accepts
        filtered = {k: v for k, v in kwargs.items()
                    if k in self._ACCEPTED_KWARGS}
        super().__init__(host, port=port, **filtered)

        self.ws_endpoint = (
            "ws://" + str(self.dev_host) + ":" + str(self.ws_port) +
            "/ws/home/overview"
        )
        self.ws_token = ""
        self.dev_type = ""
        self.dev_code = ""

    def connect(self):
        if self.ws_token:
            return True

        try:
            self.ws_socket = create_connection(
                self.ws_endpoint, timeout=self.timeout
            )
        except Exception as err:
            logging.debug(
                f"Connection to websocket server failed: "
                f"{self.ws_endpoint}, Message: {err}"
            )
            return None

        logging.debug(
            "Connection to websocket server established: " + self.ws_endpoint
        )

        self.ws_socket.send(json.dumps({
            "lang": "en_us", "token": self.ws_token, "service": "connect"
        }))
        try:
            result = self.ws_socket.recv()
        except Exception as err:
            result = ""
            raise ConnectionException(f"Websocket error: {str(err)}")

        try:
            payload_dict = json.loads(result)
            logging.debug(payload_dict)
        except Exception as err:
            raise ConnectionException(
                f"Data error: {str(result)}\n\t\t\t\t{str(err)}"
            )

        if payload_dict['result_msg'] == 'success':
            self.ws_token = payload_dict['result_data']['token']
            logging.info("Token Retrieved: " + self.ws_token)
        else:
            self.ws_token = ""
            raise ConnectionException(
                f"Connection Failed {payload_dict['result_msg']}"
            )

        logging.debug("Requesting Device Information")
        self.ws_socket.send(json.dumps({
            "lang": "en_us", "token": self.ws_token,
            "service": "devicelist", "type": "0", "is_check_token": "0"
        }))
        result = self.ws_socket.recv()
        payload_dict = json.loads(result)
        logging.debug(payload_dict)

        if payload_dict['result_msg'] == 'success':
            self.dev_type = payload_dict['result_data']['list'][0]['dev_type']
            self.dev_code = payload_dict['result_data']['list'][0]['dev_code']
            logging.debug(
                "Retrieved: dev_type = " + str(self.dev_type) +
                ", dev_code = " + str(self.dev_code)
            )
        else:
            logging.warning("Connection Failed", payload_dict['result_msg'])
            raise ConnectionException(self.__str__())

        return self.ws_socket is not None

    def close(self):
        return self.ws_socket is None

    @property
    def connected(self):
        return self.ws_socket is not None

    def send(self, request, addr=None):
        if not self.ws_token:
            self.connect()

        self.header = request

        if str(request[7]) == '4':
            param_type = 0
        elif str(request[7]) == '3':
            param_type = 1

        address = (256 * request[8] + request[9]) + 1
        count = 256 * request[10] + request[11]
        dev_id = str(request[6])
        self.payload_modbus = ""

        logging.debug(
            "param_type: " + str(param_type) +
            ", start_address: " + str(address) +
            ", count: " + str(count) +
            ", dev_id: " + str(dev_id)
        )
        url = (
            f'http://{str(self.dev_host)}/device/getParam?'
            f'dev_id={dev_id}&dev_type={str(self.dev_type)}'
            f'&dev_code={str(self.dev_code)}&type=3'
            f'&param_addr={address}&param_num={count}'
            f'&param_type={str(param_type)}&token={self.ws_token}'
            f'&lang=en_us&time123456={str(int(time.time()))}'
        )
        logging.debug(f'Calling: {url}')
        try:
            r = requests.get(url, timeout=self.timeout)
        except Exception as err:
            raise ConnectionException(f"HTTP Request failed: {str(err)}")

        logging.debug("HTTP Status code " + str(r.status_code))
        if str(r.status_code) == '200':
            self.payload_dict = json.loads(str(r.text))
            logging.debug(
                "Payload Status code " +
                str(self.payload_dict.get('result_code', "N/A"))
            )
            logging.debug("Payload Dict: " + str(self.payload_dict))
            if self.payload_dict.get('result_code', 0) == 1:
                modbus_data = (
                    self.payload_dict['result_data']['param_value'].split(' ')
                )
                modbus_data.pop()
                data_len = int(len(modbus_data))
                logging.debug("Data length: " + str(data_len))
                self.payload_modbus = [
                    '00', format(request[1], '02x'),
                    '00', '00', '00', format((data_len + 3), '02x'),
                    format(request[6], '02x'), format(request[7], '02x'),
                    format(data_len, '02x')
                ]
                self.payload_modbus.extend(modbus_data)
                return self.payload_modbus
            elif self.payload_dict.get('result_code', 0) == 106:
                self.ws_token = ""
                raise ConnectionException(
                    f"Token Expired: "
                    f"{str(self.payload_dict.get('result_code'))}:"
                    f"{str(self.payload_dict.get('result_msg'))} "
                )
            else:
                raise ConnectionException(
                    f"Connection Failed: "
                    f"{str(self.payload_dict.get('result_code'))}:"
                    f"{str(self.payload_dict.get('result_msg'))} "
                )
        else:
            raise ConnectionException(
                f"Connection Failed: "
                f"{str(self.payload_dict.get('result_code'))}:"
                f"{str(self.payload_dict.get('result_msg'))} "
            )

    def recv(self, size):
        if not self.payload_modbus:
            logging.error("Receive Failed: payload is empty")
            raise ConnectionException(self.__str__())

        if size is None:
            recv_size = 4096
        else:
            recv_size = size

        data = []
        counter = 0
        time_ = time.time()

        logging.debug("Modbus payload: " + str(self.payload_modbus))

        for temp_byte in self.payload_modbus:
            if temp_byte:
                data.append(bytes.fromhex(temp_byte))
                time_ = time.time()

            counter += 1
            if counter == recv_size:
                break

        del self.payload_modbus[0:counter]

        logging.debug(
            "Requested Size: " + str(size) +
            ", Returned Size: " + str(counter)
        )

        if int(counter) < int(size):
            raise ConnectionException(
                f"Short read: got {counter} bytes, expected {size}"
            )

        return b"".join(data)

    def __str__(self):
        return "SungrowModbusWebClient_%s(%s:%s)" % (
            __version__, self.dev_host, self.ws_port
        )

    def __repr__(self):
        return (
            "<{} at {} socket={self.ws_socket}, ipaddr={self.dev_host}, "
            "port={self.ws_port}, timeout={self.timeout}>"
        ).format(self.__class__.__name__, hex(id(self)), self=self)
