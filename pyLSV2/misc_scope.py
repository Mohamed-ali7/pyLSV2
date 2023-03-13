#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""misc helper functions for the scope part of pyLSV2"""
import struct
from datetime import datetime
from typing import List
import logging

from . import const as lc
from . import misc as lm
from . import dat_cls as ld
from .err import LSV2ProtocolException


logger = logging.getLogger("LSV2 Client Scope")


def decode_signal_description(data_set: bytearray) -> List[ld.ScopeSignal]:
    """decode the data returned from R_OC / S_OC"""
    # print(data_set)
    # data_set[  0:  2] : channel number
    # data_set[  2:  4] : 1. copy of interval value
    # data_set[  4:  6] : channel/signal type
    # data_set[  6:  8] : ? always 0x0000
    # data_set[  8: 10] : 2. copy of interval value
    # data_set[ 46: ??] : name of the channel
    # type 1, 2, 4, 5:
    # data_set[ 59:   ] : signal names
    signals = list()
    channel_number = struct.unpack("!H", data_set[0:2])[0]
    name_start = 46
    name_end = 46
    zero_byte_found = False
    while zero_byte_found is False:
        if data_set[name_end] == 0x00:
            zero_byte_found = True
        else:
            name_end += 1
    channel_name = lm.ba_to_ustr(data_set[name_start:name_end])
    if data_set[10:46] != bytearray(b"\x00" * 36):
        raise LSV2ProtocolException(
            "unexpected data in channel description in bytes 10 to 45: %s",
            data_set[10:46],
        )
    interval_value_1 = struct.unpack("!H", data_set[2:4])[0]
    interval_value_2 = struct.unpack("!H", data_set[8:10])[0]
    if interval_value_1 != interval_value_2:
        raise LSV2ProtocolException(
            "error in decoding of channel description data: %s" % data_set
        )

    min_interval = interval_value_1
    type_num = struct.unpack("!H", data_set[4:6])[0]
    if not lc.ChannelType.has_value(type_num):
        raise LSV2ProtocolException("unexpected numerical value for type %d" % type_num)

    channel_type = lc.ChannelType(type_num)
    if not data_set[6:8] == bytearray(b"\x00\x00"):
        raise LSV2ProtocolException(
            "unexpected values in bytes 6 and 7: %s" % data_set[6:8]
        )
    if channel_type in [lc.ChannelType.TYPE1, lc.ChannelType.TYPE4]:
        if len(data_set) != 106:
            raise LSV2ProtocolException(
                "unexpected length of data for chennel type 1 or 4"
            )

        axes_start = 59
        axes_end = 105
        for i, signal_label in enumerate(
            lm.ba_to_ustr(data_set[axes_start:axes_end]).split(chr(0x00))
        ):
            if signal_label == "-":
                continue
            sig_desc = ld.ScopeSignal()
            sig_desc.channel_name = channel_name
            sig_desc.channel = channel_number
            sig_desc.min_interval = min_interval
            sig_desc.channel_type = channel_type
            sig_desc.signal_name = signal_label
            sig_desc.signal = i
            signals.append(sig_desc)
    elif channel_type == lc.ChannelType.TYPE0:
        if len(data_set) != 59:
            raise LSV2ProtocolException("unexpected length of data for chennel type 0")

        sig_desc = ld.ScopeSignal()
        sig_desc.channel_name = channel_name
        sig_desc.channel = channel_number
        sig_desc.min_interval = min_interval
        sig_desc.channel_type = channel_type
        signals.append(sig_desc)
    else:
        if len(data_set) != 94:
            raise LSV2ProtocolException(
                "unexpected length of data for chennel type 2 or 5"
            )

        type_start = 59
        type_end = 93
        for i, signal_label in enumerate(
            lm.ba_to_ustr(data_set[type_start:type_end]).split(chr(0x00))
        ):
            if signal_label == "-":
                continue
            sig_desc = ld.ScopeSignal()
            sig_desc.channel_name = channel_name
            sig_desc.channel = channel_number
            sig_desc.min_interval = min_interval
            sig_desc.channel_type = channel_type
            sig_desc.signal_name = signal_label
            sig_desc.signal = i
            signals.append(sig_desc)
    return signals


def decode_system_information(data_set: bytearray):
    """decode data reurned by R_CI / S_CI"""
    logger.debug("R_CI result is %d bytes of %s" % (len(data_set), data_set))
    # always returns b"\x00\x00\x00\x02\x00\x00\x0b\xb8" for recording 1, 2 and 3
    # -> is independent of channel, axes, interval or samples
    # maybe the last four bytes are the actual interval? 0x00 00 0b b8 = 3000
    # documentation hints
    if data_set != bytearray(b"\x00\x00\x00\x02\x00\x00\x0b\xb8"):
        print(" # unexpected return pattern for R_CI!")
        raise Exception("unknown data for S_CI result")
    return data_set


def decode_signal_details(
    signal_list: List[ld.ScopeSignal], data_set: bytearray
) -> List[ld.ScopeSignal]:
    """ "decode data reurned by R_OP / S_OP"""
    logger.debug("step 2: R_OP result is %d bytes", len(data_set))
    # contains further description of the channel?
    # list with signals is updated place!
    def split_dataset(data):
        for i in range(0, len(data), 22):
            yield data[i : i + 22]

    if (len(data_set) % 22) == 0:
        logger.debug("R_OP dataset has expected length")
        for i, data_sub_set in enumerate(split_dataset(data_set)):
            if data_sub_set[17:] != bytearray(b"?\x00\x00\x00\x00"):
                raise Exception(
                    "unexpected data in signal details at position 17 %s"
                    % data_sub_set[17:]
                )

            signal_list[i].unit = lm.ba_to_ustr(data_sub_set[0:10])
            signal_list[i].factor = struct.unpack("<d", data_sub_set[10:18])[0]
            signal_list[i].offset = struct.unpack("!l", data_sub_set[18:])[0]
            logger.debug(
                "updated signal %s / %s with unit %s, factor %f and offset %d",
                signal_list[i].channel_name,
                signal_list[i].signal_name,
                signal_list[i].unit,
                signal_list[i].factor,
                signal_list[i].offset,
            )
    else:
        logger.error(
            "R_OP dataset has unexpected length %d of %s", len(data_set), data_set
        )
    return signal_list


def decode_scope_reading(
    signal_list: List[ld.ScopeSignal],
    data_set: bytearray,
) -> ld.ScopeReading:
    """
    convert bytearray returned by R_OD / S_OD into signals

    :param signal_list: list of the requested signals
    :param data_set: bytes to decode
    """
    logger.debug("step 4/5: R_OD result is %d bytes", len(data_set))
    reading = ld.ScopeReading(int(struct.unpack("!L", data_set[0:4])[0]))

    sig_data_lenth = 134
    if int((len(data_set) - 4) / len(signal_list)) != sig_data_lenth:
        raise LSV2ProtocolException("unexpected legth of signal package")

    sig_data_start = 4
    sig_data_end = sig_data_start + sig_data_lenth

    for signal in signal_list:
        logger.debug(
            "decode data for channel %d signal %d", signal.channel, signal.signal
        )
        sig_data = ld.ScopeSignalData(channel=signal.channel, signal=signal.signal, offset=signal.offset, factor=signal.factor, unit=signal.unit)

        header = data_set[sig_data_start : sig_data_start + 6]
        if header != bytearray(b"\x00\x20\xff\xff\xff\xff"):
            raise LSV2ProtocolException("unknown signal header format")

        unpack_string = "!32l"
        value_start = sig_data_start + 6
        sig_data.data.extend(
            struct.unpack(unpack_string, data_set[value_start:sig_data_end])
        )

        reading.add_dataset((sig_data))

        sig_data_start += sig_data_lenth
        sig_data_end += sig_data_lenth

    # reading["header"] = data_set[4:56]
    # reading["data"] = data_set[56:]
    # print("reading has sequenc number %d" % reading["number"] )
    # print("reading header: %s" % reading["header"])
    # print("length of reading section: %d" % len(reading["data"]))
    logger.debug("finished decoding data for %s signals", len(signal_list))
    return reading

def dump_signal_description(signal_mapping, output_path):
    """dump list of ScopeSignal to json file"""
    pass