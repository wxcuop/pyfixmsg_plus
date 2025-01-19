Pyfixmsg_exp
========

![Lifecycle:Experimental](https://img.shields.io/badge/Lifecycle-Experimental-339999)

``pyfixmsgexp``is a library for parsing, manipulating and serialising [FIX](http://www.fixtradingcommunity.org)
messages, primarily geared towards testing forked from https://github.com/morganstanley/pyfixmsg with experminal fixsession management supporting TCP and SSL fix sessions

Objectives
-----------
 * provide a rich API to compare and manipulate messages. 
 * (mostly) Message type agnostic,
 * (mostly) value types agnostic
 * pluggable : load specification XML files, custom specifications or build your own Specification class for repeating
 groups definitions and message types, define your own codec for custom serialisation or deserialisation quirks.


Dependencies
------------
 * ``six`` library (at least version 1.12.0).
 * Optional [lxml](http://lxml.de) for faster parsing of xml specification files.
 * Optional pytest to run the tests.
 * Optional [spec files from quickfix](https://github.com/quickfix/quickfix/tree/master/spec) to get started with 
 standard FIX specifications.
 
 
Core classes
------------
 * `FixMessage`. Inherits from ``dict``. Workhorse class. By default comes with a codec that will parse standard-looking
 ``FIX``, but without support repeating groups.
 * `Codec` defines how to parse a buffer into a FixMessage, and how to serialise it back
 * `Spec` defines the ``FIX`` specification to follow. Only required for support of repeating group. Defined from 
 Quickfix's spec XML files.
 * `FixSession` defines the base ``FIX`` session logic for TCP and SSL connectivity.
 

How to run the tests
--------------------
 * ``py.test --spec=/var/tmp/FIX50.xml`` will launch the tests against the spec file in /var/tmp. You will need to load
 the [spec files from quickfix](https://github.com/quickfix/quickfix/tree/master/spec) to get the tests to work. 
 The spec files are not included in this distribution.


Notes
-----
This is  a FIX message library that includes simple  FIX session management system.  It does not contain an order management 
core, or anything similar. It is purely message parsing-manipulation-serialisation and focused on testing. 

More documentation
------------------
Read the [documentation](http://pyfixmsg.readthedocs.io/), or browse the [examples](examples/pyfixmsg_example.py) file for 
many examples

 
