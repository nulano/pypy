from rpython.rlib.buffer import Buffer
from rpython.rtyper.lltypesystem import rffi

# XXX not the most efficient implementation


class RawFFIBuffer(Buffer):
    _immutable_fields_ = ['datainstance', 'readonly']

    def __init__(self, datainstance):
        self.datainstance = datainstance
        self.readonly = False

    def getlength(self):
        return self.datainstance.getrawsize()

    def getitem(self, index):
        ll_buffer = self.datainstance.ll_buffer
        return ll_buffer[index]

    def setitem(self, index, char):
        ll_buffer = self.datainstance.ll_buffer
        ll_buffer[index] = char

    def get_raw_address(self):
        ll_buffer = self.datainstance.ll_buffer
        return rffi.cast(rffi.CCHARP, ll_buffer)
