import gzip
from io import BytesIO
from collections import defaultdict

class FIXTools:
    FIX_SEP = '\x01'
    REPEATING_GROUP_TYPE_LEG = "leg"
    REPEATING_GROUP_TYPE_ALTID = "altid"

    def __init__(self, en=None, version=None, strict=False):
        self.strict = strict
        self.notifier = en
        self.dic_wx = []
        self.dic_block_instrument = []
        self.dic_block_instrument_leg = []
        self.dic_block_instrument_alt_id = []
        if version:
            self._initialize_dictionaries(version)

    def _initialize_dictionaries(self, version):
        if version == "4.2":
            self.dic_wx.extend(["269", "270", "15", "271", "272", "273", "274", "275", "336", "276", "277", "282", "283", "284", "286", "59", "432", "126", "110", "18", "287", "37", "299", "288", "289", "346", "290", "58", "354", "355", "207", "387"])
            self.dic_block_instrument_leg.extend(["308", "309", "10456", "311", "310", "319", "313", "314", "315", "316", "54"])
        elif version == "4.4":
            self.dic_wx.extend(["269", "270", "15", "271", "272", "273", "274", "275", "336", "336", "625", "277", "282", "283", "284", "286", "59", "432", "126", "110", "18", "287", "37", "299", "288", "289", "346", "290", "546", "811", "58", "354", "355"])
            self.dic_block_instrument.extend(["55", "65", "48", "22", "454", "455", "456", "461", "167", "762", "200", "541", "224", "225", "239", "226", "227", "228", "255", "543", "470", "471", "472", "240", "202", "947", "206", "231", "223", "207", "106", "348", "349", "107", "350", "351", "691", "667", "875", "876", "864", "865", "866", "867", "868", "873", "874"])
            self.dic_block_instrument_leg.extend(["600", "601", "602", "603", "604", "605", "606", "607", "608", "609", "764", "610", "611", "248", "249", "250", "251", "252", "253", "257", "599", "596", "597", "598", "254", "612", "942", "613", "614", "615", "616", "617", "618", "619", "620", "621", "622", "623", "624", "556", "740", "739", "955", "956"])
            self.dic_block_instrument_alt_id.extend(["455", "456"])

    def add_values_dic(self, values):
        self.dic_wx.extend(values)

    def get_all_tags(self, fix_message):
        tags = {}
        while self.FIX_SEP in fix_message:
            tag, fix_message = fix_message.split(self.FIX_SEP, 1)
            key, value = tag.split('=', 1)
            tags[key] = [key, value]
        return self._sort_tags(tags)

    def _sort_tags(self, tags):
        sorted_keys = sorted(tags.keys(), key=int)
        return [tags[key] for key in sorted_keys]

    def get_field(self, fix_message, field, sep=FIX_SEP):
        if f"{sep}{field}=" in fix_message:
            return fix_message.split(f"{sep}{field}=", 1)[1].split(sep, 1)[0]
        return ""

    def get_long_field(self, fix_message, tag_number):
        value = self.get_field(fix_message, str(tag_number))
        return int(value) if value else None

    def get_float_field(self, fix_message, tag_number):
        value = self.get_field(fix_message, str(tag_number))
        return float(value) if value else None

    def get_integer_field(self, fix_message, tag_number):
        value = self.get_field(fix_message, str(tag_number))
        return int(value) if value else None

    def get_tab_field(self, fix_message, field):
        values = []
        while f"{self.FIX_SEP}{field}=" in fix_message:
            fix_message = fix_message.split(f"{self.FIX_SEP}{field}=", 1)[1]
            value = fix_message.split(self.FIX_SEP, 1)[0]
            values.append(value)
            fix_message = fix_message.rsplit(f"{self.FIX_SEP}{field}=", 1)[0] + self.FIX_SEP
        return values

    def zip(self, fix_head, data):
        with BytesIO() as baos, gzip.GzipFile(fileobj=baos, mode='w') as zip_file:
            zip_file.write(data.encode('ISO-8859-1'))
            uncompressed_bytes = baos.getvalue()
        res = uncompressed_bytes.decode('ISO-8859-1')
        return f"{fix_head}01{self.FIX_SEP}{res}{self.FIX_SEP}10=000{self.FIX_SEP}"

    def unzip(self, data):
        data = data.split(self.FIX_SEP, 2)[-1][:-8]
        data_bytes = data.encode('ISO-8859-1')
        with BytesIO(data_bytes) as bios, BytesIO() as baos:
            with gzip.GzipFile(fileobj=bios, mode='rb') as unzip:
                while True:
                    chunk = unzip.read(1024)
                    if not chunk:
                        break
                    baos.write(chunk)
            return baos.getvalue().decode('ISO-8859-1')

    def add_field(self, fix_message, field, value):
        if f"{self.FIX_SEP}10=" in fix_message:
            fix_message = fix_message.rsplit(f"{self.FIX_SEP}10=", 1)[0]
        return f"{fix_message}{self.FIX_SEP}{field}={value}{self.FIX_SEP}10=000{self.FIX_SEP}"

    def change_field(self, fix_message, field, new_value):
        if f"{self.FIX_SEP}{field}=" in fix_message:
            s_tmp = fix_message.split(f"{self.FIX_SEP}{field}=", 1)[1].split(self.FIX_SEP, 1)[1]
            fix_message = fix_message.rsplit(f"{self.FIX_SEP}{field}=", 1)[0] + f"{self.FIX_SEP}{field}={new_value}{self.FIX_SEP}{s_tmp}"
        else:
            fix_message = self.add_field(fix_message, field, new_value)
        return fix_message

    def remove_field(self, fix_message, field):
        if f"{self.FIX_SEP}{field}=" in fix_message:
            s_tmp = fix_message.split(f"{self.FIX_SEP}{field}=", 1)[1]
            if self.FIX_SEP in s_tmp:
                s_tmp = s_tmp.split(self.FIX_SEP, 1)[1]
                fix_message = fix_message.rsplit(f"{self.FIX_SEP}{field}=", 1)[0] + self.FIX_SEP + s_tmp
            else:
                fix_message = fix_message.rsplit(f"{self.FIX_SEP}{field}=", 1)[0] + self.FIX_SEP
        return fix_message

    def new_size_new_checksum(self, fix_message):
        size = len(fix_message) - 20 - len(self.get_field(fix_message, "9"))
        fix_message = self.change_field(fix_message, "9", str(size))
        return self.new_checksum(fix_message)

    def new_checksum(self, fix_message):
        fix_message = self.remove_field(fix_message, "10")
        return f"{fix_message}10={self.checksum(fix_message)}{self.FIX_SEP}"

    def checksum(self, fix_message):
        checksum_value = sum(ord(char) for char in fix_message) % 256
        return f"{checksum_value:03}"

    def get_repeating_group_data(self, nb_values, repeat_group_string, delimit_tag, group_type):
        if repeat_group_string.startswith(self.FIX_SEP):
            if not self.get_field(repeat_group_string, delimit_tag):
                raise ValueError(f"Repeating group does not have mandatory first tag {delimit_tag}\t{repeat_group_string}")
        else:
            if not self.get_field(self.FIX_SEP + repeat_group_string, delimit_tag):
                raise ValueError(f"Repeating group does not have mandatory first tag {delimit_tag}\t{repeat_group_string}")

        res = []
        leg_entries = repeat_group_string

        for _ in range(nb_values):
            group_data = []
            if f"{self.FIX_SEP}{delimit_tag}=" in leg_entries:
                s_tmp = leg_entries.split(f"{self.FIX_SEP}{delimit_tag}=", 1)[0]
                leg_entries = leg_entries.split(f"{self.FIX_SEP}{delimit_tag}=", 1)[1]
            else:
                s_tmp = leg_entries

            while self.FIX_SEP in s_tmp:
                tag, s_tmp = s_tmp.split('=', 1)
                if group_type == self.REPEATING_GROUP_TYPE_LEG and not self.is_block_instrument_leg(tag):
                    break
                if group_type == self.REPEATING_GROUP_TYPE_ALTID and not self.is_block_instrument_alt_id(tag):
                    break
                value, s_tmp = s_tmp.split(self.FIX_SEP, 1)
                group_data.append([tag, value])

            res.append(group_data)

        return res, leg_entries

    def is_block_instrument_leg(self, tag):
        return tag in self.dic_block_instrument_leg

    def is_block_instrument_alt_id(self, tag):
        return tag in self.dic_block_instrument_alt_id

    def get_dictionary_fields_one_instrument_per_req(self, fix_message, delimit_tag, delimit_tag_leg):
        if f"{self.FIX_SEP}{delimit_tag}=" not in fix_message:
            raise ValueError(f"no tag {delimit_tag} to parse instrument")

        s_tmp = fix_message.split(f"{self.FIX_SEP}{delimit_tag}=", 1)[1].split(f"{self.FIX_SEP}10=", 1)[0]
        dic_entry = []
        legs = None

        while self.FIX_SEP in s_tmp:
            tag, s_tmp = s_tmp.split('=', 1)
            value, s_tmp = s_tmp.split(self.FIX_SEP, 1)
            dic_entry.append([tag, value])

            if tag == "146" and int(value) > 0:
                legs, s_tmp = self.get_repeating_group_data(int(value), s_tmp, delimit_tag_leg, self.REPEATING_GROUP_TYPE_LEG)

        return DicEntry(dic_entry, legs)

class DicEntry:
    def __init__(self, tags=None, legs=None):
        self.tags = tags or []
        self.legs = legs or []

    def set_tags(self, tags):
        self.tags = tags

    def set_legs(self, legs):
        self.legs = legs

    def get_tags(self):
        return self.tags

    def get_legs(self):
        return self.legs
