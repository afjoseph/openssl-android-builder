import os
import requests
from path import Path
from optparse import OptionParser
from loguru import logger
import subprocess
import shutil
import atexit

# OpenSSL configure options (see INSTALL.md in the root of the OpenSSL source
# for more info). Feel free to modify as needed:
# * no-filenames: don't include filenames in the libraries
# * no-ui: don't include UI code
# * no-ui-console: don't include UI code (backwards-compatible)
#   https://github.com/openssl/openssl/issues/11551
# * no-engine: don't include engine code
# * no-stdio: don't include stdio code (since Android doesn't have stdio.h)
# * -fPIC: build position-independent code
#   You can pass compile flags to the configure script by setting the
#   -f flag
OPENSSL_CONFIGURE_OPTIONS = "-fPIC no-ui no-ui-console no-engine no-filenames no-stdio"


def main(options, args):
    # Validation
    if not options.openssl_version:
        raise Exception("Please specify OpenSSL version to build")
    if not options.android_api:
        raise Exception("Please specify Android API level to build for")
    if not options.android_archs:
        raise Exception("Please specify Android architectures to build for")
    options.dist_path = os.path.realpath(options.dist_path)
    archs = options.android_archs.split(",")
    for arch in archs:
        if arch not in ["arm", "arm64", "x86", "x86_64"]:
            raise Exception("Invalid architecture: {}".format(arch))
    # Check Android NDK path and toolchain
    android_ndk_home = os.getenv("ANDROID_NDK_HOME")
    if not android_ndk_home:
        raise Exception("Please set ANDROID_NDK_HOME environment variable")
    uname = os.uname().sysname.lower()
    p = Path("{}/toolchains/llvm/prebuilt".format(android_ndk_home))
    if not p.exists():
        raise Exception(
            "Please set ANDROID_NDK_HOME environment variable to the correct path"
        )
    if len(p.dirs()) != 1:
        raise Exception("Failed to find a suitable toolchain")
    toolchain_bin_path = Path("{}/bin".format(p.dirs()[0]))

    logger.info(
        "Build params: openssl_version={}, android_api={}, android_archs={}".format(
            options.openssl_version, options.android_api, options.android_archs
        )
    )

    # Download openssl
    download_path = Path("/tmp/openssl-{}.tar.gz".format(options.openssl_version))
    shutil.rmtree(download_path, ignore_errors=True)
    logger.info("Downloading OpenSSL to {}".format(download_path))
    r = requests.get(
        "https://www.openssl.org/source/openssl-{}.tar.gz".format(
            options.openssl_version
        ),
        allow_redirects=True,
    )
    with open(download_path, "wb") as f:
        f.write(r.content)
    atexit.register(lambda: shutil.rmtree(download_path, ignore_errors=True))

    # Untar
    src_path = Path("/tmp/openssl-{}".format(options.openssl_version))
    shutil.rmtree(src_path, ignore_errors=True)
    os.makedirs(src_path)
    logger.info("Untarring OpenSSL to {}".format(src_path))
    try:
        subprocess.check_output("tar xf {} -C /tmp".format(download_path), shell=True)
    except subprocess.CalledProcessError:
        raise Exception("Failed to untar OpenSSL")
    if not src_path.exists():
        raise Exception("Failed to untar OpenSSL to correct path")
    atexit.register(lambda: shutil.rmtree(src_path, ignore_errors=True))

    # Nuke dist path to start fresh
    shutil.rmtree(options.dist_path, ignore_errors=True)

    # Build for each arch
    with src_path:
        for arch in archs:
            logger.info("Building OpenSSL for {}".format(arch))
            try:
                env = os.environ.copy()
                env["ANDROID_NDK_HOME"] = android_ndk_home
                env["ANDROID_API"] = options.android_api
                env["PATH"] = "{}:{}".format(toolchain_bin_path, env["PATH"])
                env["CC"] = "clang"
                subprocess.check_output(
                    "./Configure android-{} {}".format(arch, OPENSSL_CONFIGURE_OPTIONS),
                    shell=True,
                    env=env,
                    stderr=subprocess.STDOUT,
                )
                subprocess.check_output(
                    "make",
                    shell=True,
                    env=env,
                    stderr=subprocess.STDOUT,
                )
            except subprocess.CalledProcessError as e:
                raise Exception(
                    "Failed to configure OpenSSL for {}: {}".format(arch, e.output)
                )

            logger.info("Building for {} done. Copying libs...".format(arch))
            arch_dist_path = Path("{}/{}".format(options.dist_path, arch))
            os.makedirs(arch_dist_path)
            for lib in [
                "libssl.a",
                "libcrypto.a",
                "libssl.so",
                "libcrypto.so",
            ]:
                src_lib_path = Path(lib)
                dst_lib_path = Path("{}/{}".format(arch_dist_path, lib))
                if not src_lib_path.exists():
                    raise Exception("Failed to find {} library".format(lib))
                logger.info("Copying {} to {}".format(src_lib_path, dst_lib_path))
                shutil.copyfile(
                    src_lib_path,
                    dst_lib_path,
                )

    # Copy include directory
    # This should be done **after** the ./configure script is run at least once
    # (doesn't matter the architecture) since the file
    # "include/openssl/opensslconf.h" defines some macros that reflect the
    # chosen configure options.
    logger.info("Copying OpenSSL include directory to {}".format(options.dist_path))
    shutil.copytree(
        "{}/include".format(src_path),
        "{}/include".format(options.dist_path),
    )
    logger.info("Done")


if __name__ == "__main__":
    try:
        parser = OptionParser()
        parser.add_option(
            "--openssl_version",
            dest="openssl_version",
            default="1.1.1t",
            help="OpenSSL version to build. Defaults to '1.1.1t'",
        )
        parser.add_option(
            "--android_api",
            dest="android_api",
            default="21",
            help="Android API level to build for. Defaults to '21'",
        )
        parser.add_option(
            "--android-archs",
            dest="android_archs",
            default="arm64",
            help="comma-separated list of android architectures to build for. Defaults to 'arm64'. Valid values are 'arm', 'arm64', 'x86', 'x86_64'",
        )
        parser.add_option(
            "--dist-path",
            dest="dist_path",
            default="dist",
            help="Path to store the built OpenSSL libraries. Defaults to 'dist'",
        )
        (options, args) = parser.parse_args()
        main(options, args)
    except KeyboardInterrupt:
        logger.info("Exiting...")
