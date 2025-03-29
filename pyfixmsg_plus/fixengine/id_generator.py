import time
import datetime
import logging
import string
from typing import Optional


class ClientOrderIdGenerator:
    """
    Abstract base class for client order ID generators.
    """

    def decode(self, to_be_decoded, length):
        raise NotImplementedError

    def encode(self, to_be_encoded):
        raise NotImplementedError


class NumericClOrdIdGenerator(ClientOrderIdGenerator):
    """
    Generates unique ClOrdIDs seeded with a passed-in number (e.g. endpoint id).
    """

    def __init__(self, eid, length=10, seed=True):
        self.length = length
        self.uid = 0
        self.seed = seed
        self.max_cl_ord_id = 10**(length - 1)  # Max ClOrdID based on length
        self.endpoint_modulo = 10**(length - 8)  # Endpoint modulo based on length
        self.time_divisor = 86400 // (10**(length - 9))  # Time divisor based on length
        self.init(eid)

    def init(self, eid):
        if self.length < 10:
            raise ValueError("Smallest supported NumericClOrdIdGenerator length is 10")

        self.uid = 0
        self.uid += eid % self.endpoint_modulo

        segment = 1
        if self.seed:
            now = int(time.time())
            segment = now % 86400
            segment //= self.time_divisor
            segment += 1
            if segment == 5:
                segment += 1

        self.uid += segment * self.endpoint_modulo
        self.uid *= self.max_cl_ord_id
        logging.debug(f"Initialized numeric ClOrdID generator with UID prefix = [{self.uid}] eid [{eid}]")

    def decode(self, to_be_decoded):
        return int(to_be_decoded) - self.uid

    def encode(self, to_be_encoded):
        if to_be_encoded >= self.max_cl_ord_id:
            raise ValueError("Max ClOrdID exceeded")
        return str(self.uid + to_be_encoded)


class YMDClOrdIdGenerator(NumericClOrdIdGenerator):
    """
    Generates unique ClOrdIDs with a YMD prefix.
    """

    def __init__(self, eid, seed=True):
        super().__init__(eid, 10, seed)
        self.ymd_prefix = self.init_ymd_prefix()

    def init_ymd_prefix(self):
        convert = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        today = datetime.datetime.now(datetime.UTC)
        year_prefix = convert[today.year % 36]
        month_prefix = convert[today.month]
        day_prefix = convert[today.day]
        return f"{year_prefix}{month_prefix}{day_prefix}-"

    def decode(self, to_be_decoded):
        return super().decode(to_be_decoded[4:])

    def encode(self, to_be_encoded):
        if to_be_encoded >= self.max_cl_ord_id:
            raise ValueError("Max ClOrdID exceeded")
        cl_ord_id = super().encode(tobe_encoded)
        return f"{self.ymd_prefix}{cl_ord_id}"


class BMESeqGenerator(ClientOrderIdGenerator):
    """
    Generates unique ClOrdIDs with a fixed prefix.
    """

    def __init__(self, prefix):
        if not prefix or len(prefix) > 20:
            raise ValueError("Prefix length should be less than or equal to 20.")
        self.id_prefix = prefix.ljust(20, '0')

    def encode(self, to_be_encoded):
        if not isinstance(to_be_encoded, int):
            raise ValueError("Input should be an integer.")
        return f"{self.id_prefix}{tobe_encoded:010d}"

    def decode(self, to_be_decoded):
        if not to_be_decoded or len(to_be_decoded) != 30:
            return -1
        try:
            return int(to_be_decoded[20:])
        except ValueError:
            return -1


class BranchSeqIdGenerator(ClientOrderIdGenerator):
    """
    Generates unique ClOrdIDs with a branch sequence.
    """

    class Type:
        CBOE = "CBOE"

    def __init__(self, str_value, type_value):
        self.type = type_value
        self.today_date = time.strftime("%Y%m%d", time.localtime())
        self.start, self.end = self.init_ranges(str_value)

    def init_ranges(self, str_value):
        parts = str_value.split('-')
        if len(parts) == 1:
            parts.append("ZZZ")

        start_str = f"{parts[0]:<3}0001"
        end_str = f"{parts[1]:<3}9999"

        start = self.decode(start_str) - 1
        end = self.decode(end_str)

        logging.debug(f"Id generator: date {self.today_date} start {start_str} {start} end {end_str} {end}")
        return start, end

    def get_mapped_seq_no(self, in_seq_no):
        num_skips = (in_seq_no - 1) // 9999
        return num_skips + in_seq_no + self.start

    def get_seq_no_from_mapped(self, mapped_seq_no):
        return mapped_seq_no

    def decode(self, to_be_decoded):
        if len(to_be_decoded) < 7:
            return -1

        if not (to_be_decoded[0].isalpha() and to_be_decoded[1].isalpha() and to_be_decoded[2].isalpha()):
            return -1

        branch_seq = to_be_decoded[3:] if to_be_decoded[3] != ' ' else to_be_decoded[4:]
        if not all(c.isdigit() for c in branch_seq):
            return -1

        ret = ((ord(to_be_decoded[0]) - ord('A')) * 26 + (ord(to_be_decoded[1]) - ord('A'))) * 26 + (ord(to_be_decoded[2]) - ord('A'))
        for i in range(4):
            ret = ret * 10 + int(branch_seq[i])
        return self.get_seq_no_from_mapped(ret)

    def encode(self, to_be_encoded):
        if to_be_encoded == 0:
            logging.error("Encoded id should be > 0")
            return ""

        mapped_seq_no = self.get_mapped_seq_no(tobe_encoded)
        if mapped_seq_no > self.end:
            logging.error("Id generator allocation ended, cannot allocate anymore")
            return ""

        branch = [None] * 3
        branch_seq = [None] * 4

        for i in range(3):
            branch_seq[3 - i] = chr(mapped_seq_no % 10 + ord('0'))
            mapped_seq_no //= 10

        for i in range(3):
            branch[2 - i] = chr(mapped_seq_no % 26 + ord('A'))
            mapped_seq_no //= 26

        if self.type == self.Type.CBOE:
            return f"{''.join(branch)}{''.join(branch_seq)}-{self.today_date}"
        return ""


class ESPSeqGenerator(ClientOrderIdGenerator):
    """
    Generates unique ClOrdIDs with a fixed prefix.
    """

    def __init__(self, prefix):
        if not prefix or len(prefix) > 10:
            raise ValueError("Prefix length should be less than or equal to 10.")
        self.id_prefix = prefix.ljust(10, '0')

    def encode(self, to_be_encoded):
        if not isinstance(to_be_encoded, int):
            raise ValueError("Input should be an integer.")
        return f"{self.id_prefix}{tobe_encoded:010d}"

    def decode(self, to_be_decoded):
        if not to_be_decoded or len(to_be_decoded) != 20:
            return -1
        try:
            return int(to_be_decoded[10:])
        except ValueError:
            return -1


class KSESeqGenerator(ClientOrderIdGenerator):
    """
    Generates unique ClOrdIDs with a fixed prefix.
    """

    PSE_SEQ_LENGTH = 10

    def __init__(self, prefix):
        if not prefix or len(prefix) > 1:
            raise ValueError("Prefix length should be equal to 1.")
        self.id_prefix = prefix.ljust(1, '0')

    def encode(self, to_be_encoded):
        if not isinstance(to_be_encoded, int):
            raise ValueError("Input should be an integer.")
        return f"{self.id_prefix}{tobe_encoded:09d}"

    def decode(self, to_be_decoded):
        if not to_be_decoded or len(to_be_decoded) != self.PSE_SEQ_LENGTH:
            return -1
        try:
            return int(to_be_decoded[1:])
        except ValueError:
            return -1


class MonthClOrdIdGenerator(NumericClOrdIdGenerator):
    """
    Generates unique ClOrdIDs with a day-of-month prefix.
    """

    def __init__(self, eid, seed=True):
        super().__init__(eid, 13, seed)
        self.day_index = self.init_day_index()

    def init_day_index(self):
        today = datetime.datetime.now(datetime.UTC).day
        if today < 26:
            return chr(ord('A') + today)
        else:
            return chr(ord('a') + today - 26)

    def decode(self, to_be_decoded):
        return super().decode(to_be_decoded[1:])

    def encode(self, to_be_encoded):
        if to_be_encoded >= self.max_cl_ord_id:
            raise ValueError("Max ClOrdID exceeded")
        cl_ord_id = super().encode(tobe_encoded)
        return f"{self.day_index}{cl_ord_id}"


class NyseBranchSeqGenerator(ClientOrderIdGenerator):
    """
    Generates unique ClOrdIDs with a NYSE branch sequence.
    """

    RESERVED_BRANCH_CODE = lambda Char1, Char2, Char3: (((ord(Char1) - ord('A')) * 26 + (ord(Char2) - ord('A'))) * 26 + (ord(Char3) - ord('A'))) * 10000

    skipped = [
        RESERVED_BRANCH_CODE('H', 'M', 'Q'),
        RESERVED_BRANCH_CODE('Q', 'Q', 'Q'),
        RESERVED_BRANCH_CODE('R', 'R', 'R'),
        RESERVED_BRANCH_CODE('T', 'T', 'T'),
        RESERVED_BRANCH_CODE('Y', 'Y', 'Y'),
        RESERVED_BRANCH_CODE('Z', 'Y', 'X'),
        RESERVED_BRANCH_CODE('Z', 'Y', 'Y'),
        RESERVED_BRANCH_CODE('Z', 'Y', 'Z'),
        RESERVED_BRANCH_CODE('Z', 'Z', 'Z'),
    ]

    def __init__(self, s, sep):
        if not s:
            raise ValueError(f"NyseBranchSeqGenerator: wrong parameter = {s}")
        if len(s) > 7:
            raise ValueError(f"NyseBranchSeqGenerator: wrong parameter = {s}")
        if '-' not in s:
            raise ValueError(f"NyseBranchSeqGenerator: wrong parameter = {s}")

        self.min_ = self.get_min(s, s.split('-')[0])
        if self.min_ == -1:
            raise ValueError(f"NyseBranchSeqGenerator: wrong parameter = {s}")

        for skipped in self.skipped:
            if self.min_ * 10000 == skipped:
                raise ValueError(f"NyseBranchSeqGenerator: starting branch code is reserved: {s}")

        self.max_ = self.get_max(s.split('-')[1], s)
        if self.max_ == -1 or self.max_ < self.min_:
            raise ValueError(f"NyseBranchSeqGenerator: wrong parameter = {s}")

        self.min_ *= 10000
        self.max_ = self.max_ * 10000 + 9999
        self.available_ids_ = self.get_total_num_of_available_ids(self.min_, self.max_)
        self.init_min()
        self.num_of_skips_for_min_ = self.min_ // 10000

        if self.available_ids_ <= 0:
            raise ValueError(f"NyseBranchSeqGenerator: wrong parameter = {s}")

        logging.info(f"Total available ids for {s} = {self.available_ids_}")
        logging.info(f"Number of skips of min for {s} = {self.num_of_skips_for_min_}")
        logging.info(f"Index skipped by min for {s} = {self.idx_skipped_by_min_}")

        now = time.localtime()
        self.id_template_ = f"XXX{sep}NNNN/{time.strftime('%m%d%Y', now)}"

        logging.info(f"Min = {self.min_}, Max = {self.max_}")

    def get_min(self, p_start, p_end):
        if len(p_end) - len(p_start) > 3:
            return -1

        buf = ['A', 'A', 'A']
        i = 0
        for p in p_start:
            if p.isupper():
                buf[i] = p
                i += 1
            else:
                return -1

        return (ord(buf[0]) - ord('A')) * 26 * 26 + (ord(buf[1]) - ord('A')) * 26 + ord(buf[2]) - ord('A')

    def get_max(self, p_start, p_end):
        if len(p_end) - len(p_start) > 3:
            return -1

        buf = ['Z', 'Z', 'Z']
        i = 0
        for p in p_start:
            if p.isupper():
                buf[i] = p
                i += 1
            else:
                return -1

        return (ord(buf[0]) - ord('A')) * 26 * 26 + (ord(buf[1]) - ord('A')) * 26 + ord(buf[2]) - ord('A')

    def get_total_num_of_available_ids(self, t_begin, t_end):
        num_skips = (t_end - t_begin) // 10000
        for skipped in self.skipped:
            if t_begin > skipped + 9999:
                continue
            elif t_end > skipped:
                num_skips += 9999
            else:
                return t_end - t_begin - num_skips

        return t_end - t_begin - num_skips

    def init_min(self):
        for i in range(5):
            if self.min_ == self.skipped[i]:
                self.idx_skipped_by_min_ = i + 1
                self.min_ += 10000
                return
            elif self.min_ < self.skipped[i]:
                return
            else:
                self.idx_skipped_by_min_ = i + 1

        self.idx_skipped_by_min_ = 5

        if self.min_ < self.skipped[5]:
            return

        for i in range(3, 0, -1):
            if self.min_ == self.skipped[5 + i]:
                self.min_ += 10000 * i
                return

        self.idx_skipped_by_min_ = 8

    def get_nth_id(self, seqno):
        num_skips = (seqno - 1) // 9999
        ret = seqno + num_skips + self.min_

        if self.idx_skipped_by_min_ == 8:
            return ret

        for i in range(self.idx_skipped_by_min_, 5):
            if ret < self.skipped[i]:
                return ret
            else:
                ret += 10000

        if ret < self.skipped[5]:
            return ret

        if ret < self.skipped[8]:
            return ret + 30000

        return -1

    def decode(self, to_be_decoded):
        if not to_be_decoded or len(to_be_decoded) != 17:
            return -1

        num = 0
        alpha = 0

        for p in to_be_decoded[4:8]:
            if not p.isdigit():
                return -1
            num = num * 10 + int(p)

        for p in to_be_decoded[:3]:
            if not p.isupper():
                return -1
            alpha = alpha * 26 + (ord(p) - ord('A'))

        return self.get_total_num_of_available_ids(self.min_, alpha * 10000 + num)

    def encode(self, tobe_encoded):
        if tobe_encoded > self.available_ids_:
            return ""

        tobe_encoded = self.get_nth_id(tobe_encoded)
        encoded = list(self.id_template_)

        num = tobe_encoded % 10000
        alpha = tobe_encoded // 10000

        for p in range(7, 3, -1):
            rem = num % 10
            encoded[p] = chr(ord('0') + rem)
            num //= 10

        for p in range(2, -1, -1):
            rem = alpha % 26
            encoded[p] = chr(ord('A') + rem)
            alpha //= 26

        return "".join(encoded)


class OSESeqGenerator(ClientOrderIdGenerator):
    """
    Generates unique ClOrdIDs with a fixed prefix.
    """

    def __init__(self, prefix):
        if not prefix or len(prefix) > 10:
            raise ValueError("Prefix length should be less than or equal to 10.")
        self.id_prefix = prefix.ljust(10, '0')

    def encode(self, to_be_encoded):
        if not isinstance(to_be_encoded, int):
            raise ValueError("Input should be an integer.")
        return f"{self.id_prefix}{tobe_encoded:010d}"

    def decode(self, to_be_decoded):
        if not to_be_decoded or len(to_be_decoded) != 20:
            return -1
        try:
            return int(to_be_decoded[10:])
        except ValueError:
            return -1

class CHIXBranchSeqGenerator(NyseBranchSeqGenerator):
    """
    Generates unique ClOrdIDs with a CHIX branch sequence.
    """

    def __init__(self, s):
        super().__init__(s, '_')
