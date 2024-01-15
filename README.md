# OpenSSL Android Builder

Configuring OpenSSL for Android [is not particularly hard](https://wiki.openssl.org/index.php/Android) but it's cumbersome to remember all the steps. This script was tested with NDK 26 on an OSX machine to build OpenSSL 1.1.1t.

Different configurations on different machines might require changing the script a bit. Feel free to commit your changes or report the issues on your setup.

## Usage

    poetry init
    # Will build with sane values.
    # Use -h to use advanced flags
    poetry run python3 main.py
