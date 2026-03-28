#!/usr/bin/python3

import logging
import logging.handlers
import time
from datetime import datetime
from typing import Any

from pymodbus.client import ModbusTcpClient

from version import __version__
from .sungrow_modbus_tcp_client import SungrowModbusTcpClient
from .sungrow_modbus_web_client import SungrowModbusWebClient

class SungrowClient():
    def __init__(self, config_inverter):

        logging.info('Loading SungrowClient %s', __version__)

        self.client_config = {
            "host":     config_inverter.get('host'),
            "port":     config_inverter.get('port'),
            "timeout":  config_inverter.get('timeout'),
            "retries":  config_inverter.get('retries'),
        }
        self.inverter_config = {
            "model":            config_inverter.get('model'),
            "serial_number":    config_inverter.get('serial_number'),
            "level":            config_inverter.get('level'),
            "scan_interval":    config_inverter.get('scan_interval'),
            "use_local_time":   config_inverter.get('use_local_time'),
            "smart_meter":      config_inverter.get('smart_meter'),
            "connection":       config_inverter.get('connection'),
            "slave":            config_inverter.get('slave'),
            "start_time":       ""
        }
        self.client = None

        self.registers: list[dict[str, Any]] = []
        self.registers_custom = [
            {'name': 'run_state', 'address': 'vr001'},
            {'name': 'timestamp', 'address': 'vr002'},
            {'name': 'last_reset', 'address': 'vr003'},
            {'name': 'export_to_grid', 'unit': 'W', 'address': 'vr004'},
            {'name': 'import_from_grid', 'unit': 'W', 'address': 'vr005'},
            {'name': 'daily_export_to_grid', 'unit': 'kWh', 'address': 'vr006'},
            {'name': 'daily_import_from_grid', 'unit': 'kWh', 'address': 'vr007'},
        ]

        self.register_ranges: list[dict[str, Any]] = []

        self.latest_scrape: dict[str, Any] = {}

    def connect(self) -> bool:
        if self.client:
            try:
                self.client.connect()
            except Exception:  # pylint: disable=broad-exception-caught
                return False
            return True

        host = self.client_config['host']
        config = {k: v for k, v in self.client_config.items() if k != 'host'}

        if self.inverter_config['connection'] == "http":
            config['port'] = 8082
            # host passed as keyword — SungrowModbusWebClient declares it with a default,
            # unlike the other clients
            self.client = SungrowModbusWebClient(host=host, **config)
        elif self.inverter_config['connection'] == "sungrow":
            self.client = SungrowModbusTcpClient(host, **config)
        elif self.inverter_config['connection'] == "modbus":
            self.client = ModbusTcpClient(host, **config)
        else:
            logging.warning(
                "Inverter: Unknown connection type %s, Valid options are http, sungrow or modbus",
                self.inverter_config['connection']
            )
            return False
        logging.info("Connection: %s", self.client)

        try:
            self.client.connect()
        except Exception:  # pylint: disable=broad-exception-caught
            return False

        time.sleep(3)
        return True

    def checkConnection(self) -> bool:
        logging.debug("Checking Modbus Connection")
        if self.client:
            if self.client.connected:
                logging.debug("Modbus, Session is still connected")
                return True
            logging.info('Modbus, Connecting new session')
            return self.connect()
        logging.info('Modbus client is not connected, attempting to reconnect')
        return self.connect()

    def close(self):
        logging.info("Closing Session: %s", self.client)
        try:
            self.client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def disconnect(self):
        logging.info("Disconnecting: %s", self.client)
        try:
            self.client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        self.client = None

    # -------------------------------------------------------------------------
    # configure_registers helpers
    # -------------------------------------------------------------------------

    def _detect_field(self, field_name, scan_start, scan_range, scan_type):
        """Load registers and extract a single field value for auto-detection."""
        if self.load_registers(scan_type, scan_start, scan_range):
            value = self.latest_scrape.get(field_name)
            if isinstance(value, int):
                logging.warning("Unknown Type Code Detected: %s", value)
                return None
            return value
        return None

    def _filter_registers_by_level(self, raw_registers, reg_type):
        """Filter register list by level, model compatibility, and smart_meter flag."""
        level = self.inverter_config.get('level')
        model = self.inverter_config.get('model')
        smart_meter = self.inverter_config.get('smart_meter')

        for register in raw_registers:
            if not (register.get('level', 3) <= level or level == 3):
                continue
            register['type'] = reg_type
            register.pop('level')
            if register.get('smart_meter') and smart_meter:
                register.pop('models')
                self.registers.append(register)
            elif register.get('models') and not level == 3:
                for supported_model in register.get('models'):
                    if supported_model == model:
                        register.pop('models')
                        self.registers.append(register)
            else:
                self.registers.append(register)

    def _build_register_ranges(self, scan_read_list, scan_hold_list):
        """Build register_ranges from scan config."""
        for reg_range in scan_read_list:
            reg_range['type'] = "read"
            if self._is_range_used(reg_range):
                self.register_ranges.append(reg_range)

        for reg_range in scan_hold_list:
            reg_range['type'] = "hold"
            if self._is_range_used(reg_range):
                self.register_ranges.append(reg_range)

    def _is_range_used(self, register_range) -> bool:
        """Return True if any register falls within this scan range."""
        for register in self.registers:
            if register.get("type") != register_range.get("type"):
                continue
            addr = register.get('address')
            rng_start = register_range.get("start")
            rng_end = rng_start + register_range.get("range")
            if rng_start <= addr <= rng_end:
                return True
        return False

    def configure_registers(self, registersfile) -> bool:
        # Check model so we can load only valid registers
        if self.inverter_config.get('model'):
            logging.info(
                "Bypassing Model Detection, Using config: %s", self.inverter_config.get('model')
            )
        else:
            self._auto_detect_model(registersfile)

        if self.inverter_config.get('serial_number'):
            logging.info(
                "Bypassing Serial Detection, Using config: %s",
                self.inverter_config.get('serial_number')
            )
        else:
            self._auto_detect_serial(registersfile)

        self._filter_registers_by_level(registersfile['registers'][0]['read'], "read")
        self._filter_registers_by_level(registersfile['registers'][1]['hold'], "hold")
        self._build_register_ranges(
            registersfile['scan'][0]['read'],
            registersfile['scan'][1]['hold'],
        )
        return True

    def _auto_detect_model(self, registersfile):
        """Detect inverter model from device_type_code register."""
        for register in registersfile['registers'][0]['read']:
            if register.get('name') == "device_type_code":
                register['type'] = "read"
                self.registers.append(register)
                detected = self._detect_field(
                    "device_type_code", register['address'] - 1, 1, register['type']
                )
                if detected is not None:
                    self.inverter_config['model'] = detected
                    logging.info("Detected Model: %s", detected)
                else:
                    logging.info('Model detection failed, please set model in config.py')
                self.registers.pop()
                break

    def _auto_detect_serial(self, registersfile):
        """Detect inverter serial number from serial_number register."""
        for register in registersfile['registers'][0]['read']:
            if register.get('name') == "serial_number":
                register['type'] = "read"
                self.registers.append(register)
                detected = self._detect_field(
                    "serial_number", register['address'] - 1, 10, register['type']
                )
                if detected is not None:
                    self.inverter_config['serial_number'] = detected
                    logging.info("Detected Serial: %s", detected)
                else:
                    logging.info(
                        'Serial detection failed, please set serial number in config.py'
                    )
                self.registers.pop()
                break

    # -------------------------------------------------------------------------
    # load_registers helpers
    # -------------------------------------------------------------------------

    def _decode_datatype(self, register, raw_registers, index):
        """Convert raw register word(s) to a Python value based on datatype."""
        register_value = raw_registers[index]
        datatype = register.get('datatype')

        if datatype == "U16":
            if register_value == 0xFFFF:
                register_value = 0
            if register.get('mask'):
                register_value = 1 if register_value & register.get('mask') != 0 else 0
        elif datatype == "S16":
            if register_value in (0xFFFF, 0x7FFF):
                register_value = 0
            if register_value >= 32767:  # Anything > 32767 is negative for 16bit
                register_value = register_value - 65536
        elif datatype == "U32":
            register_value = self._decode_u32(register_value, raw_registers[index + 1])
        elif datatype == "S32":
            register_value = self._decode_s32(register_value, raw_registers[index + 1])
        elif datatype == "UTF-8":  # Serial only, 10 bytes
            utf_value = register_value.to_bytes(2, 'big')
            for x in range(1, 5):
                utf_value += raw_registers[index + x].to_bytes(2, 'big')
            register_value = utf_value.decode()

        return register_value

    def _decode_u32(self, low, high):
        """Decode U32 value from two 16-bit words."""
        if low == 0xFFFF and high == 0xFFFF:
            return 0
        return low + high * 0x10000

    def _decode_s32(self, low, high):
        """Decode S32 value from two 16-bit words."""
        s32_zero = high in (0xFFFF, 0x7FFF)
        if low == 0xFFFF and s32_zero:
            return 0
        if high >= 32767:  # Anything greater than 32767 is a negative
            return low + high * 0x10000 - 0xffffffff - 1
        return low + high * 0x10000

    def _decode_register_value(self, register, raw_registers, index):
        """Decode a raw register value with datatype conversion, datarange, and accuracy."""
        register_value = self._decode_datatype(register, raw_registers, index)

        # We convert a system response to a human value
        if register.get('datarange'):
            match = False
            for value in register.get('datarange'):
                if value['response'] == raw_registers[index]:
                    register_value = value['value']
                    match = True
            if not match:
                default = register.get('default')
                logging.debug(
                    "No matching value for %s in datarange of %s, using default %s",
                    register_value, register['name'], default
                )
                register_value = default

        if register.get('accuracy'):
            register_value = round(register_value * register.get('accuracy'), 2)

        return register_value

    def load_registers(self, register_type, start, count=100) -> bool:
        try:
            logging.debug('load_registers: %s, %s:%s', register_type, start, count)
            if register_type == "read":
                rr = self.client.read_input_registers(
                    start, count=count, device_id=self.inverter_config['slave']
                )
            elif register_type == "hold":
                rr = self.client.read_holding_registers(
                    start, count=count, device_id=self.inverter_config['slave']
                )
            else:
                raise RuntimeError(f"Unsupported register type: {type}")
        except Exception as err:  # pylint: disable=broad-exception-caught
            logging.warning("No data returned for %s, %s:%s", register_type, start, count)
            logging.debug("%s", err)
            return False

        if rr.isError():
            logging.warning("Modbus connection failed")
            logging.debug("%s", rr)
            return False

        if not hasattr(rr, 'registers'):
            logging.warning("No registers returned")
            return False

        if len(rr.registers) != count:
            logging.warning(
                "Mismatched number of registers read %s != %s", len(rr.registers), count
            )
            return False

        for num in range(0, count):
            run = int(start) + num + 1
            for register in self.registers:
                if register_type == register['type'] and register['address'] == run:
                    self.latest_scrape[register['name']] = self._decode_register_value(
                        register, rr.registers, num
                    )
        return True

    def validateRegister(self, check_register) -> bool:
        for register in self.registers:
            if check_register == register['name']:
                return True
        for register in self.registers_custom:
            if check_register == register['name']:
                return True
        return False

    def getRegisterAddress(self, check_register) -> int | str | None:
        for register in self.registers:
            if check_register == register['name']:
                return register['address']
        for register in self.registers_custom:
            if check_register == register['name']:
                return register['address']
        return '----'

    def getRegisterUnit(self, check_register) -> str:
        for register in self.registers:
            if check_register == register['name']:
                return register.get('unit','')
        for register in self.registers_custom:
            if check_register == register['name']:
                return register.get('unit','')
        return ''

    def validateLatestScrape(self, check_register) -> bool:
        for register, _value in self.latest_scrape.items():
            if check_register == register:
                return True
        return False

    def getRegisterValue(self, check_register) -> Any:
        for register, value in self.latest_scrape.items():
            if check_register == register:
                return value
        return False

    def getHost(self) -> str | None:
        return self.client_config['host']

    def getInverterModel(self, clean=False) -> str:
        if clean:
            return self.inverter_config['model'].replace('.','').replace('-','')
        return self.inverter_config['model']

    def getSerialNumber(self) -> str | None:
        return self.inverter_config['serial_number']

    # -------------------------------------------------------------------------
    # scrape helpers
    # -------------------------------------------------------------------------

    def _assemble_timestamp(self):
        """Build timestamp string and remove individual time registers."""
        time_keys = ["year", "month", "day", "hour", "minute", "second"]
        if self.inverter_config.get('use_local_time', False):
            self.latest_scrape["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.debug('Using Local Computer Time: %s', self.latest_scrape.get("timestamp"))
        else:
            try:
                s = self.latest_scrape
                self.latest_scrape["timestamp"] = (
                    f"{s['year']}-{s['month']}-{s['day']}"
                    f" {s['hour']}:{s['minute']:02d}:{s['second']:02d}"
                )
                logging.debug('Using Inverter Time: %s', self.latest_scrape.get("timestamp"))
            except Exception:  # pylint: disable=broad-exception-caught
                self.latest_scrape["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logging.warning(
                    'Failed to get Timestamp from Inverter, using Local Time: %s',
                    self.latest_scrape.get("timestamp")
                )
        for key in time_keys:
            self.latest_scrape.pop(key, None)

    def _assemble_alarm_timestamp(self):
        """Build alarm timestamp from alarm_time_* registers, then remove them."""
        alarm_keys = [
            "alarm_time_year", "alarm_time_month", "alarm_time_day",
            "alarm_time_hour", "alarm_time_minute", "alarm_time_second",
        ]
        try:
            if self.latest_scrape["pid_alarm_code"]:
                s = self.latest_scrape
                self.latest_scrape["alarm_timestamp"] = (
                    f"{s['alarm_time_year']}-{s['alarm_time_month']}-{s['alarm_time_day']}"
                    f" {s['alarm_time_hour']}:{s['alarm_time_minute']:02d}"
                    f":{s['alarm_time_second']:02d}"
                )
            for key in alarm_keys:
                del self.latest_scrape[key]
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _compute_run_state(self):
        """Determine ON/OFF based on start_stop and work_state_1."""
        try:
            if self.latest_scrape.get('start_stop'):
                logging.debug(
                    "start_stop:%s work_state_1:%s",
                    self.latest_scrape.get('start_stop', 'null'),
                    self.latest_scrape.get('work_state_1', 'null')
                )
                work_state = self.latest_scrape.get('work_state_1', False)
                if (self.latest_scrape.get('start_stop', False) == 'Start'
                        and 'Run' in work_state):
                    self.latest_scrape["run_state"] = "ON"
                else:
                    self.latest_scrape["run_state"] = "OFF"
            else:
                logging.info("DEBUG: Couldn't read start_stop so run_state is OFF")
                self.latest_scrape["run_state"] = "OFF"
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _compute_grid_power(self):
        """Calculate export_to_grid/import_from_grid from meter_power or export_power_hybrid."""
        self.latest_scrape["export_to_grid"] = 0
        self.latest_scrape["import_from_grid"] = 0

        if self.validateRegister('meter_power'):
            try:
                power = self.latest_scrape.get(
                    'meter_power', self.latest_scrape.get('export_power', 0)
                )
                if power < 0:
                    self.latest_scrape["export_to_grid"] = abs(power)
                elif power >= 0:
                    self.latest_scrape["import_from_grid"] = power
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        elif self.validateRegister('export_power_hybrid'):
            # export_power_hybrid is negative in case of importing from the grid
            try:
                power = self.latest_scrape.get('export_power_hybrid', 0)
                if power < 0:
                    self.latest_scrape["import_from_grid"] = abs(power)
                elif power >= 0:
                    self.latest_scrape["export_to_grid"] = power
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    def _compute_load_power(self):
        """Calculate load_power_hybrid from total_active_power and meter_power if missing."""
        try:
            if not self.latest_scrape["load_power"]:
                self.latest_scrape["load_power"] = (
                    int(self.latest_scrape.get('total_active_power'))
                    + int(self.latest_scrape.get('meter_power'))
                )
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _reset_daily_totals_if_needed(self):
        """Reset daily counters on midnight rollover (vr003)."""
        date_format = "%Y-%m-%d %H:%M:%S"
        if not self.latest_scrape.get('last_reset', False):
            logging.info(
                'Setting Initial Daily registers; '
                'daily_export_to_grid, daily_import_from_grid, last_reset'
            )
            self.latest_scrape["daily_export_to_grid"] = 0
            self.latest_scrape["daily_import_from_grid"] = 0
            self.latest_scrape['last_reset'] = self.latest_scrape["timestamp"]
        elif (datetime.strptime(self.latest_scrape['last_reset'], date_format).date()
              < datetime.strptime(self.latest_scrape['timestamp'], date_format).date()):
            logging.info(
                'last_reset: %s, timestamp: %s',
                self.latest_scrape['last_reset'], self.latest_scrape['timestamp']
            )
            logging.info(
                'Resetting Daily registers; '
                'daily_export_to_grid, daily_import_from_grid, last_reset'
            )
            self.latest_scrape["daily_export_to_grid"] = 0
            self.latest_scrape["daily_import_from_grid"] = 0
            self.latest_scrape['last_reset'] = self.latest_scrape["timestamp"]

    def _accumulate_daily_grid_totals(self):
        """Accumulate daily export/import totals from current scrape interval (vr006/vr007)."""
        if not self.latest_scrape.get('daily_export_to_grid', False):
            self.latest_scrape["daily_export_to_grid"] = 0
        self.latest_scrape["daily_export_to_grid"] += (
            (self.latest_scrape["export_to_grid"] / 1000)
            * (self.inverter_config['scan_interval'] / 60 / 60)
        )

        if not self.latest_scrape.get('daily_import_from_grid', False):
            self.latest_scrape["daily_import_from_grid"] = 0
        self.latest_scrape["daily_import_from_grid"] += (
            (self.latest_scrape["import_from_grid"] / 1000)
            * (self.inverter_config['scan_interval'] / 60 / 60)
        )

    def scrape(self) -> bool:
        scrape_start = datetime.now()

        # Clear previous inverter values, persist some values
        persist_registers = {
            "run_state":                self.latest_scrape.get("run_state","ON"),
            "last_reset":               self.latest_scrape.get("last_reset",""),
            "daily_export_to_grid":     self.latest_scrape.get("daily_export_to_grid",0),
            "daily_import_from_grid":   self.latest_scrape.get("daily_import_from_grid",0),
        }

        self.latest_scrape = {}
        self.latest_scrape['device_type_code'] = self.inverter_config['model']

        for register, value in persist_registers.items():
            self.latest_scrape[register] = value

        load_registers_count = 0
        load_registers_failed = 0

        for reg_range in self.register_ranges:
            load_registers_count += 1
            logging.debug(
                'Scraping: %s, %s:%s',
                reg_range.get("type"), reg_range.get("start"), reg_range.get("range")
            )
            rng_type = reg_range.get('type')
            rng_start = int(reg_range.get('start'))
            rng_range = int(reg_range.get('range'))
            if not self.load_registers(rng_type, rng_start, rng_range):
                load_registers_failed += 1

        if load_registers_failed == load_registers_count:
            self.disconnect()
            return False
        if load_registers_failed > 0:
            logging.info(
                'Scraping: %s/%s registers failed to scrape',
                load_registers_failed, load_registers_count
            )

        self._assemble_timestamp()          ## vr002
        self._assemble_alarm_timestamp()

        ### Custom Registers
        ######################

        self._compute_run_state()           ## vr001
        self._reset_daily_totals_if_needed() ## vr003

        ## vr004 / vr005 - import_from_grid, export_to_grid
        if self.inverter_config['level'] >= 1:
            self._compute_grid_power()

        self._compute_load_power()

        ## vr006 / vr007 - daily totals accumulation
        self._accumulate_daily_grid_totals()

        scrape_end = datetime.now()
        elapsed = scrape_end - scrape_start
        logging.info(
            'Inverter: Successfully scraped in %s.%s secs',
            elapsed.seconds, elapsed.microseconds
        )

        return True
