#!/bin/env python
"""
Updated pyfixmsg_example.py illustrating the usage of FixMessage and associated objects,
with additional examples for FixInitiator and FixAcceptor.
"""

from __future__ import print_function

import os
import sys
import decimal
import argparse
from copy import copy
from random import randint

# Add the pyfixmsg parent directory to sys.path for import resolution
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from pyfixmsg import RepeatingGroup
from pyfixmsg.fixmessage import FixMessage, FixFragment
from pyfixmsg.reference import FixSpec, FixTag
from pyfixmsg.codecs.stringfix import Codec
from fixsession import FixInitiator, FixAcceptor

# In Python 3, 'unicode' does not exist; define it for consistency
if sys.version_info.major >= 3:
    unicode = str  # pylint: disable=C0103,W0622


def main(spec_filename):
    """
    Demonstrates how to parse, manipulate, and copy FIX messages using pyfixmsg.

    :param spec_filename: Full path to the FIX specification file (e.g., FIX42.xml).
    :type spec_filename: str
    """

    # Load the FIX 4.2 specification. Adjust as needed for other FIX versions.
    spec = FixSpec(spec_filename)

    # Create a codec to handle parsing and serializing FIX messages with the loaded spec.
    # The fragment_class ensures that repeating groups are interpreted as separate fragments.
    codec = Codec(
        spec=spec,
        fragment_class=FixFragment
    )

    def fixmsg(*args, **kwargs):
        """
        Factory function to create FixMessage instances with a default codec.
        This allows you to create messages without explicitly passing a codec each time.
        """
        returned = FixMessage(*args, **kwargs)
        returned.codec = codec
        return returned

    # --------------------------------------------------------------------------
    # Example 1: Parsing and inspecting a vanilla tag/value FIX message
    # --------------------------------------------------------------------------
    data = (
        b'8=FIX.4.2|9=97|35=6|49=ABC|56=CAB|34=14|52=20100204-09:18:42|'
        b'23=115685|28=N|55=BLAH|54=2|44=2200.75|27=S|25=H|10=248|'
    )

    # Create and load a FixMessage from a raw FIX string. Note: '|' is used as a separator here.
    msg = fixmsg().load_fix(data, separator='|')

    # Print the message type and corresponding spec name for clarity
    print("Message Type: {} (Name: {})".format(
        msg[35],
        spec.msg_types[msg[35]].name
    ))

    # Demonstrate retrieving a tag type from the spec, showing that 44 is Price
    print("Price {} (Python type: {}, Spec-defined type: {})".format(
        msg[44],
        type(msg[44]),
        spec.tags.by_tag(44).type
    ))

    # Check which tags are required or optional for this message type
    check_tags = (55, 44, 27)
    for element, required in spec.msg_types[msg[35]].composition:
        if isinstance(element, FixTag) and element.tag in check_tags:
            if required:
                print("{} is required by this message type".format(element.name))
            else:
                print("{} is not required by this message type".format(element.name))

    # Look up an enum definition from the spec (e.g., 54=2 might mean SELL)
    print("Tag 54 = {} (Enum: {})".format(
        msg[54],
        spec.tags.by_tag(54).enum_by_value(msg[54])
    ))

    # Demonstrate comparison methods such as tag_exact, tag_lt, tag_gt, etc.
    print("Exact comparison with Decimal:", msg.tag_exact(44, decimal.Decimal("2200.75")))
    print("Exact comparison with int:", msg.tag_exact(54, 2))
    print("Less than comparison (float):", msg.tag_lt(44, 2500.0))
    print("Greater than comparison (float):", msg.tag_gt(23, 110000.1))
    print("Contains (case-sensitive):", msg.tag_contains(55, "MI"))
    print("Contains (case-insensitive):", msg.tag_icontains(55, "blah"))

    # Demonstrate updating or changing tags
    msg[56] = "ABC.1"  # Overwrite tag 56
    msg.update({55: 'ABC123.1', 28: 'M'})  # Overwrite tags 55 and 28
    print("Regex match on tag 56:", msg.tag_match_regex(56, r"..M\.N"))
    print("Tag 55 and 28 changed to '{}' and '{}'".format(msg[55], msg[28]))

    # set_or_delete will remove a tag if the value is None, otherwise it updates it
    none_or_one = randint(0, 1) or None
    msg.set_or_delete(27, none_or_one)
    msg.apply({25: None, 26: 2})  # Set or delete multiple tags at once

    if none_or_one is None:
        print("Randomly got None, tag 27 is deleted")
        assert 27 not in msg
    else:
        print("Randomly got 1, tag 27 is set to 1")
        assert msg[27] == 1

    # Tag 25 was explicitly set to None, so it should be removed
    assert 25 not in msg
    assert msg.tag_exact(26, '2')

    # --------------------------------------------------------------------------
    # Example 2: Copying messages
    # --------------------------------------------------------------------------
    new_msg = msg.copy()
    assert new_msg is not msg
    msg.set_len_and_chksum()

    # The copy operation may transform certain fields (like 26) into typed versions vs. raw strings
    print("Tag 26 before copy: {}, after copy: {}".format(
        type(msg[26]),
        type(new_msg[26])
    ))

    # If no types have changed, copy() yields an identical but separate message object
    msg = fixmsg().load_fix(data, separator='|')
    second_msg = copy(msg)
    assert second_msg == msg
    second_msg_codec = second_msg.codec
    assert second_msg_codec is msg.codec

    # If you construct a FixMessage directly from a dictionary, the codec is not preserved
    dict_copy_msg = FixMessage(msg)
    print("Constructed from dict: Messages are equal by tags only:", dict_copy_msg == msg)
    print("But their dict content is equal:", dict_copy_msg.items() == msg.items())

    # --------------------------------------------------------------------------
    # Example 3: Repeating Groups
    # --------------------------------------------------------------------------
    data = (
        b'8=FIX.4.2|9=196|35=X|49=A|56=B|34=12|52=20100318-03:21:11.364'
        b'|262=A|268=2|279=0|269=0|278=BID|55=EUR/USD|270=1.37215'
        b'|15=EUR|271=2500000|346=1|279=0|269=1|278=OFFER|55=EUR/USD'
        b'|270=1.37224|15=EUR|271=2503200|346=1|10=171|'
    )

    msg = fixmsg().load_fix(data, separator='|')
    print("Message Type: {} (Name: {})".format(msg[35], spec.msg_types[msg[35]].name))
    print("Repeating group via tag 268: {}".format(msg[268]))
    print("Second element of repeating group, tag 278: '{}'".format(msg[268][1][278]))
    print("Checking if tag 278 exists anywhere:", msg.anywhere(278))
    print("All paths to tag 278 in the message:", list(msg.find_all(278)))

    # --------------------------------------------------------------------------
    # Example 4: Customizing the FIX Spec
    # --------------------------------------------------------------------------
    # Demonstrate adding a new tag or modifying enum values on an existing tag.
    spec.tags.add_tag(10001, "MyTagName")
    assert spec.tags.by_tag(10001).name == "MyTagName"

    spec.tags.by_tag(54).add_enum_value(name="SELLFAST", value="SF")
    assert spec.tags.by_tag(54).enum_by_value("SF") == "SELLFAST"

    # Demonstrate adding a repeating group definition to a message type, so it
    # parses recurring tags properly. For example, adding group 268 to MsgType 'D'.
    data = (
        b'8=FIX.4.2|9=196|35=D|49=A|56=B|34=12|52=20100318-03:21:11.364'
        b'|262=A|268=2|279=0|269=0|278=BID|55=EUR/USD|270=1.37215'
        b'|15=EUR|271=2500000|346=1|279=0|269=1|278=OFFER|55=EUR/USD'
        b'|270=1.37224|15=EUR|271=2503200|346=1|10=171|'
    )

    before = FixMessage()
    before.codec = Codec(spec=spec)
    before.load_fix(data, separator='|')

    # Create a composition array of (tag, is_required). For demonstration.
    composition = [(spec.tags.by_tag(i), False) for i in (279, 269, 278, 55, 270, 15, 271, 346)]
    spec.msg_types['D'].add_group(spec.tags.by_tag(268), composition)

    after = FixMessage()
    after.codec = Codec(spec=spec, fragment_class=FixFragment)
    after.load_fix(data, separator='|')

    # before[268] is a normal tag, after[268] is parsed as a repeating group
    print("Before adding repeating group, tag 268 type:", type(before[268]))
    print("After adding repeating group, tag 268 type:", type(after[268]))

    # Shows how the repeating group is parsed into separate fragments
    print("Repeating group for message type 'D':", after[268])

    # Confirm that 270 is recognized in both entries of the repeating group
    paths_for_270 = list(after.find_all(270))
    print("Paths for tag 270 within repeating group:", paths_for_270)

    # --------------------------------------------------------------------------
    # Example 5: Implementing FixInitiator and FixAcceptor
    # --------------------------------------------------------------------------

    # Configuration for the initiator and acceptor roles
    config_path = 'config.ini'

    # Example usage for FixInitiator
    def run_initiator():
        initiator = FixInitiator(config_path)
        initiator.start()

    # Example usage for FixAcceptor
    def run_acceptor():
        acceptor = FixAcceptor(config_path)
        acceptor.start()

    # Uncomment one of the following lines to run the example
    # run_initiator()
    # run_acceptor()


if __name__ == "__main__":
    PARSER = argparse.ArgumentParser(
        description="Example usage of pyfixmsg to parse, manipulate, and copy FIX messages."
    )
    PARSER.add_argument("spec_xml", help="Path to the FIX specification XML file (e.g., FIX42.xml).")
    args = PARSER.parse_args()
    main(args.spec_xml)
