# Code by Simon Monk https://github.com/simonmonk/

import logging
import time

from . import MFRC522
import RPi.GPIO as GPIO
import sys


class SimpleMFRC522:
    DEFAULT_KEY = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]

    _log_verbose = None
    _log = None
    _mfrc522 = None
    _key = None

    def __init__(self, key=None, log_verbose=True, pin_mode=GPIO.BOARD):
        self._log = logging.getLogger(self.__class__.__name__)
        self._log_verbose = log_verbose
        # Don't change the logger's level based on log_verbose
        # This ensures that ERROR messages are always logged at ERROR level
        # Instead, we'll use log_verbose to determine whether to log DEBUG messages

        if key is None:
            key = SimpleMFRC522.DEFAULT_KEY
        self._key = key
        self._mfrc522 = MFRC522(log_verbose=log_verbose, pin_mode=pin_mode)

    def read_id(self, attempts=sys.maxsize):
        id = self.read_id_no_block()
        tries = 1
        while not id and tries < attempts:
            id = self.read_id_no_block()
            tries += 1
        return id, tries

    def read_id_no_block(self):
        reqMode = self._mfrc522.PICC_REQIDL
        (status, TagType) = self._mfrc522.MFRC522_Request(reqMode)
        if status != self._mfrc522.MI_OK:
            # This error indicates no card present
            self._log.debug({
                'action': 'read_id_no_block_request_failed',
                'reqMode': f'0x{reqMode:02X}',  # Log reqMode as hex value
                'status': f'0x{status:02X}'     # Log status as hex value
            })
            return None
        (status, uid) = self._mfrc522.MFRC522_Anticoll()
        if status != self._mfrc522.MI_OK:
            self._log.error({
                'action': 'read_id_no_block_anticoll_failed',
                'status': f'0x{status:02X}'     # Log status as hex value
            })
            return None
        return self.uid_to_num(uid)

    def read(self, trailer=11, blocks=(8, 9, 10), attempts=sys.maxsize):
        id, text = self.read_no_block(trailer=trailer, blocks=blocks)
        tries = 1
        while not id and tries < attempts:
            id, text = self.read_no_block(trailer=trailer, blocks=blocks)
            tries += 1
        return id, text, tries

    def log_time(self, action, start):
        if self._log_verbose:
            end = time.time()
            self._log.debug({
                'action': action,
                'start': f'{start:.5f}',
                'end': f'{end:.5f}',
                'duration': f'{end - start:.5f}',
            })

    def log_error_with_time(self, error, status, start):
        if self._log_verbose:
            end = time.time()
            self._log.error({
                'error': error,
                'status': f'0x{status:02X}',  # Log status as hex value
                'start': f'{start:.5f}',
                'end': f'{end:.5f}',
                'duration': f'{end - start:.5f}',
            })

    def read_no_block(self, trailer=11, blocks=(8, 9, 10)):
        start = time.time()
        reqMode = self._mfrc522.PICC_REQIDL
        status, _ = self._mfrc522.MFRC522_Request(reqMode)
        if status != self._mfrc522.MI_OK:
            self.log_error_with_time('MFRC522_Request', status, start)
            if self._log_verbose:
                self._log.debug({
                    'action': 'MFRC522_Request',
                    'reqMode': f'0x{reqMode:02X}',  # Log reqMode as hex value
                    'status': f'0x{status:02X}'     # Log status as hex value
                })
            return None, None
        self.log_time('MFRC522_Request', start)
        if self._log_verbose:
            self._log.debug({
                'action': 'MFRC522_Request_Success',
                'reqMode': f'0x{reqMode:02X}',      # Log reqMode as hex value
                'status': f'0x{status:02X}'         # Log status as hex value
            })

        start = time.time()
        status, uid = self._mfrc522.MFRC522_Anticoll()
        if status != self._mfrc522.MI_OK:
            self.log_error_with_time('MFRC522_Anticoll', status, start)
            return None, None
        self.log_time('MFRC522_Anticoll', start)

        start = time.time()
        status, _ = self._mfrc522.MFRC522_SelectTag(uid)
        if status != self._mfrc522.MI_OK:
            self.log_error_with_time('MFRC522_SelectTag', status, start)
            return None, None
        self.log_time('MFRC522_SelectTag', start)

        start = time.time()
        command = self._mfrc522.PICC_AUTHENT1A
        status = self._mfrc522.MFRC522_Auth(command,
                                           trailer, self._key, uid)
        if status != self._mfrc522.MI_OK:
            self.log_error_with_time('MFRC522_Auth', status, start)
            self._log.error({
                'action': 'MFRC522_Auth_Failed',
                'command': f'0x{command:02X}',  # Log command as hex value
                'status': f'0x{status:02X}'     # Log status as hex value
            })
            return None, None
        self.log_time('MFRC522_Auth', start)
        if self._log_verbose:
            self._log.debug({
                'action': 'MFRC522_Auth_Success',
                'command': f'0x{command:02X}',      # Log command as hex value
                'status': f'0x{status:02X}'         # Log status as hex value
            })

        data = []
        text_read = ''
        if status == self._mfrc522.MI_OK:
            for block_num in blocks:
                start = time.time()
                block = self._mfrc522.MFRC522_Read(block_num)
                self.log_time('MFRC522_Read', start)
                if block:
                    data += block
            if data:
                text_read = ''.join(chr(i) for i in data)

        start = time.time()
        self._mfrc522.MFRC522_StopCrypto1()
        self.log_time('MFRC522_StopCrypto1', start)

        id = self.uid_to_num(uid)
        return id, text_read

    def write(self, text, trailer=11, blocks=(8, 9, 10), attempts=sys.maxsize):
        id, text_out = self.write_no_block(
            text, trailer=trailer, blocks=blocks)
        tries = 1
        while not id and tries < attempts:
            id, text_out = self.write_no_block(
                text, trailer=trailer, blocks=blocks)
            tries += 1
        return id, text_out, tries

    def write_no_block(self, text, trailer=11, blocks=(8, 9, 10)):
        reqMode = self._mfrc522.PICC_REQIDL
        (status, TagType) = self._mfrc522.MFRC522_Request(reqMode)
        if status != self._mfrc522.MI_OK:
            self._log.error({
                'action': 'write_no_block_request_failed',
                'reqMode': f'0x{reqMode:02X}',  # Log reqMode as hex value
                'status': f'0x{status:02X}'     # Log status as hex value
            })
            return None, None
        (status, uid) = self._mfrc522.MFRC522_Anticoll()
        if status != self._mfrc522.MI_OK:
            self._log.error({
                'action': 'write_no_block_anticoll_failed',
                'status': f'0x{status:02X}'     # Log status as hex value
            })
            return None, None
        id = self.uid_to_num(uid)
        self._mfrc522.MFRC522_SelectTag(uid)
        command = self._mfrc522.PICC_AUTHENT1A
        status = self._mfrc522.MFRC522_Auth(
            command, trailer, self._key, uid)
        if self._log_verbose:
            self._log.debug({
                'action': 'write_no_block_auth',
                'command': f'0x{command:02X}',      # Log command as hex value
                'status': f'0x{status:02X}'         # Log status as hex value
            })
        self._mfrc522.MFRC522_Read(trailer)
        if status == self._mfrc522.MI_OK:
            data = bytearray()
            data.extend(bytearray(text.ljust(len(blocks) * 16).encode('ascii')))
            i = 0
            for block_num in blocks:
                self._mfrc522.MFRC522_Write(block_num,
                                            data[(i * 16):(i + 1) * 16])
                i += 1
        self._mfrc522.MFRC522_StopCrypto1()
        return id, text[0:(len(blocks) * 16)]

    def uid_to_num(self, uid):
        n = 0
        for i in range(0, 5):
            n = n * 256 + uid[i]
        return n
