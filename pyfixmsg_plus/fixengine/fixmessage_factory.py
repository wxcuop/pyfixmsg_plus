from pyfixmsg.fixmessage import FixMessage, FixFragment
from pyfixmsg.reference import FixSpec
from pyfixmsg.codecs.stringfix import Codec


class FixMessageFactory:
    codec = None
    
    @staticmethod
    def set_codec(spec_filename):
        spec = FixSpec(spec_filename)
        FixMessageFactory.codec = Codec(spec=spec,  # The codec will use the given spec to find repeating groups
                                        fragment_class=FixFragment)  # The codec will produce FixFragment objects inside repeating groups

    @staticmethod
    def fixmsg(*args, **kwargs):
        """
        Factory function to create and return a FixMessage instance with the
        codec set to the specified spec.

        This function keeps the dictionary __init__ arguments unchanged and
        ensures the codec is set to the provided spec, thus avoiding the need
        to pass the codec to serialization and parsing methods explicitly.

        The codec defaults to a reasonable parser but does not handle repeating
        groups by default.

        Alternatively, you can use the ``to_wire`` and ``from_wire`` methods to
        serialize and parse messages and pass the codec explicitly if needed.
        """
        if FixMessageFactory.codec is None:
            raise ValueError("FixMessageFactory.codec is not initialized. Call set_codec first.")
        returned = FixMessage(*args, **kwargs)
        returned.codec = FixMessageFactory.codec
        return returned
