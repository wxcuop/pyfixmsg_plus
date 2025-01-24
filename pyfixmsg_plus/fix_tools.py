import gzip
from io import BytesIO
from collections import defaultdict

class FIXTools:
    c_FixSep = '\x01'
    repeatingGroupType_LEG = "leg"
    repeatingGroupType_ALTID = "altid"

    def __init__(self, en=None, version=None, strict=False):
        self.Strict = strict
        self.FTEN = en
        self.DIC_wx = []
        self.DIC_BlockInstrument = []
        self.DIC_BlockInstrumentLeg = []
        self.DIC_BlockInstrumentAltId = []
        if version:
            self.CommonConstructor(version)

    def CommonConstructor(self, version):
        if version == "4.2":
            self.DIC_wx.extend(["269", "270", "15", "271", "272", "273", "274", "275", "336", "276", "277", "282", "283", "284", "286", "59", "432", "126", "110", "18", "287", "37", "299", "288", "289", "346", "290", "58", "354", "355", "207", "387"])
            self.DIC_BlockInstrumentLeg.extend(["308", "309", "10456", "311", "310", "319", "313", "314", "315", "316", "54"])
        elif version == "4.4":
            self.DIC_wx.extend(["269", "270", "15", "271", "272", "273", "274", "275", "336", "336", "625", "277", "282", "283", "284", "286", "59", "432", "126", "110", "18", "287", "37", "299", "288", "289", "346", "290", "546", "811", "58", "354", "355"])
            self.DIC_BlockInstrument.extend(["55", "65", "48", "22", "454", "455", "456", "461", "167", "762", "200", "541", "224", "225", "239", "226", "227", "228", "255", "543", "470", "471", "472", "240", "202", "947", "206", "231", "223", "207", "106", "348", "349", "107", "350", "351", "691", "667", "875", "876", "864", "865", "866", "867", "868", "873", "874"])
            self.DIC_BlockInstrumentLeg.extend(["600", "601", "602", "603", "604", "605", "606", "607", "608", "609", "764", "610", "611", "248", "249", "250", "251", "252", "253", "257", "599", "596", "597", "598", "254", "612", "942", "613", "614", "615", "616", "617", "618", "619", "620", "621", "622", "623", "624", "556", "740", "739", "955", "956"])
            self.DIC_BlockInstrumentAltId.extend(["455", "456"])

    def addValuesDIC_e(self, v):
        self.DIC_wx.extend(v)

    def getAllTags(self, FIX):
        h = {}
        tmp = FIX
        while self.c_FixSep in tmp:
            tag = tmp.split(self.c_FixSep, 1)[0].split('=', 1)
            tmp = tmp.split(self.c_FixSep, 1)[1]
            h[tag[0]] = tag
        return self.sort(h)

    def sort(self, hs):
        sorted_keys = sorted(hs.keys(), key=int)
        return [hs[key] for key in sorted_keys]

    def getField(self, FIX, Field, sep=c_FixSep):
        if f"{sep}{Field}=" in FIX:
            s_tmp = FIX.split(f"{sep}{Field}=", 1)[1]
            return s_tmp.split(sep, 1)[0]
        return ""

    def getLongField(self, sFixMessage, nTagNumber):
        sField = str(nTagNumber)
        sValue = self.getField(sFixMessage, sField)
        if not sValue:
            return None
        try:
            return int(sValue)
        except ValueError:
            return None

    def getFloatField(self, sFixMessage, nTagNumber):
        sField = str(nTagNumber)
        sValue = self.getField(sFixMessage, sField)
        if not sValue:
            return None
        try:
            return float(sValue)
        except ValueError:
            return None

    def getIntegerField(self, sFixMessage, nTagNumber):
        sField = str(nTagNumber)
        sValue = self.getField(sFixMessage, sField)
        if not sValue:
            return None
        try:
            return int(sValue)
        except ValueError:
            return None

    def getTabField(self, FIX, Field):
        v = []
        while f"{self.c_FixSep}{Field}=" in FIX:
            s_tmp = FIX.split(f"{self.c_FixSep}{Field}=", 1)[1]
            s_result = s_tmp.split(self.c_FixSep, 1)[0]
            v.append(s_result)
            FIX = FIX.rsplit(f"{self.c_FixSep}{Field}=", 1)[0] + self.c_FixSep
        return v

    def zip(self, FIX_Head, data):
        with BytesIO() as baos, gzip.GzipFile(fileobj=baos, mode='w') as zip_file:
            zip_file.write(data.encode('ISO-8859-1'))
            uncompressed_bytes = baos.getvalue()
        res = uncompressed_bytes.decode('ISO-8859-1')
        return f"{FIX_Head}01{self.c_FixSep}{res}{self.c_FixSep}10=000{self.c_FixSep}"

    def unzip(self, data):
        data = data.split(self.c_FixSep, 2)[-1][:-8]
        data_bytes = data.encode('ISO-8859-1')
        with BytesIO(data_bytes) as bios, BytesIO() as baos:
            with gzip.GzipFile(fileobj=bios, mode='rb') as unzip:
                while True:
                    chunk = unzip.read(1024)
                    if not chunk:
                        break
                    baos.write(chunk)
            return baos.getvalue().decode('ISO-8859-1')

    def AddField(self, FIX, Field, Value):
        if f"{self.c_FixSep}10=" in FIX:
            s_Result = FIX.rsplit(f"{self.c_FixSep}10=", 1)[0]
        else:
            s_Result = FIX
        return f"{s_Result}{self.c_FixSep}{Field}={Value}{self.c_FixSep}10=000{self.c_FixSep}"

    def ChangeField(self, FIX, Field, newValue):
        if f"{self.c_FixSep}{Field}=" in FIX:
            s_tmp = FIX.split(f"{self.c_FixSep}{Field}=", 1)[1].split(self.c_FixSep, 1)[1]
            s_Result = FIX.rsplit(f"{self.c_FixSep}{Field}=", 1)[0] + f"{self.c_FixSep}{Field}={newValue}{self.c_FixSep}{s_tmp}"
        else:
            s_Result = self.AddField(FIX, Field, newValue)
        return s_Result

    def RemoveField(self, FIX, Field):
        if f"{self.c_FixSep}{Field}=" in FIX:
            s_tmp = FIX.split(f"{self.c_FixSep}{Field}=", 1)[1]
            if self.c_FixSep in s_tmp:
                s_tmp = s_tmp.split(self.c_FixSep, 1)[1]
                s_Result = FIX.rsplit(f"{self.c_FixSep}{Field}=", 1)[0] + self.c_FixSep + s_tmp
            else:
                s_Result = FIX.rsplit(f"{self.c_FixSep}{Field}=", 1)[0] + self.c_FixSep
        else:
            s_Result = FIX
        return s_Result

    def NewSizeNewCheckSum(self, FIX):
        size = len(FIX) - 20 - len(self.getField(FIX, "9"))
        s_Result = self.ChangeField(FIX, "9", str(size))
        s_Result = self.NewChecksum(s_Result)
        return s_Result

    def NewChecksum(self, FIX):
        s_Result = self.RemoveField(FIX, "10")
        s_Result = f"{s_Result}10={self.Checksum(s_Result)}{self.c_FixSep}"
        return s_Result

    def Checksum(self, S_FIX):
        i_tmp = sum(ord(char) for char in S_FIX) % 256
        return f"{i_tmp:03}"

    def getRepeatingGroupData(self, nbValues, repeatgroupstring, DelimitTag, type):
        if repeatgroupstring.startswith(self.c_FixSep):
            if not self.getField(repeatgroupstring, DelimitTag):
                raise Exception(f"Repeating group does not have mandatory first tag {DelimitTag}\t{repeatgroupstring}")
        else:
            if not self.getField(self.c_FixSep + repeatgroupstring, DelimitTag):
                raise Exception(f"Repeating group does not have mandatory first tag {DelimitTag}\t{repeatgroupstring}")

        Res = []
        s_tmp = ""
        LegEntries = repeatgroupstring
        for _ in range(nbValues):
            Res = []
            if f"{self.c_FixSep}{DelimitTag}=" in LegEntries:
                s_tmp = LegEntries.split(f"{self.c_FixSep}{DelimitTag}=", 1)[0]
                LegEntries = LegEntries.split(f"{self.c_FixSep}{DelimitTag}=", 1)[1]
            else:
                s_tmp = LegEntries

            while self.c_FixSep in s_tmp:
                Tags = ["", ""]
                Tags[0] = s_tmp.split('=', 1)[0]
                if type == self.repeatingGroupType_LEG:
                    if not self.isBlockInstrumentLeg(Tags[0]):
                        break
                    Tags[1] = s_tmp.split('=', 1)[1].split(self.c_FixSep, 1)[0]
                    s_tmp = s_tmp.split(self.c_FixSep, 1)[1]
                    Res.append(Tags)
                elif type == self.repeatingGroupType_ALTID:
                    if not self.isBlockInstrumentAltId(Tags[0]):
                        break
                    Tags[1] = s_tmp.split('=', 1)[1].split(self.c_FixSep, 1)[0]
                    s_tmp = s_tmp.split(self.c_FixSep, 1)[1]
                    Res.append(Tags)

            if Res:
                vs.v.append(Res)

        if "stop" in locals():
            vs.s = f";{self.c_FixSep}{s_tmp}"
        else:
            vs.s = s_tmp
        return vs

    def isBlockInstrumentLeg(self, Tag):
        return Tag in self.DIC_BlockInstrumentLeg

    def isBlockInstrumentAltId(self, Tag):
        return Tag in self.DIC_BlockInstrumentAltId

    def getDictionaryFields_OneInstrumentPerReq(self, FIX, DelimitTag, DelimitTagLeg):
        if f"{self.c_FixSep}{DelimitTag}=" not in FIX:
            raise Exception(f"no tag {DelimitTag} to parse instrument")
        s_tmp = FIX.split(f"{self.c_FixSep}{DelimitTag}=", 1)[1].split(f"{self.c_FixSep}10=", 1)[0]
        vDicEntry = []
        while self.c_FixSep in s_tmp:
            Tags = ["", ""]
            vDicEntry.append(Tags)
            Tags[0] = s_tmp.split('=', 1)[0]
            Tags[1] = s_tmp.split('=', 1)[1].split(self.c_FixSep, 1)[0]
            s_tmp = s_tmp.split(self.c_FixSep, 1)[1]

            if Tags[0] == "146":
                if int(Tags[1]) > 0:
                    vs = self.getRepeatingGroupData(int(Tags[1]), s_tmp, DelimitTagLeg, self.repeatingGroupType_LEG)
                    s_tmp = vs.s

        DE = DicEntry()
        DE.setTags(vDicEntry)
        if 'vs' in locals():
            DE.setLegs(vs.v)
        return DE

class DicEntry:
    def __init__(self):
        self._tags = []
        self._legs = []

    def setTags(self, tags):
        self._tags = tags

    def setLegs(self, legs):
        self._legs = legs

    def getTags(self):
        return self._tags

    def getLegs(self):
        return self._legs

