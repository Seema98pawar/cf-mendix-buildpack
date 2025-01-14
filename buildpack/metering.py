import logging
import os
import json
import subprocess

from buildpack import util
from buildpack.runtime_components import database

NAMESPACE = "metering"
SIDECAR_VERSION = "v1.0.1"
SIDECAR_ARCHIVE = "metering-sidecar-linux-amd64-{}.tar.gz".format(
    SIDECAR_VERSION
)
SIDECAR_URL_ROOT = "/mx-buildpack/experimental/{}".format(NAMESPACE)
SIDECAR_DIR = os.path.abspath("/home/vcap/app/metering")
SIDECAR_FILENAME = "metering-sidecar"
SIDECAR_CONFIG_FILE = "conf.json"


def _download(build_path, cache_dir):
    util.download_and_unpack(
        util.get_blobstore_url(
            "{}/{}".format(SIDECAR_URL_ROOT, SIDECAR_ARCHIVE)
        ),
        os.path.join(build_path, NAMESPACE),
        cache_dir=cache_dir,
    )


def _is_usage_metering_enabled():
    if "MXUMS_LICENSESERVER_URL" in os.environ:
        return True


def _get_project_id(file_path):
    try:
        with open(file_path) as file_handle:
            data = json.loads(file_handle.read())
            return data["ProjectID"]
    except IOError as ioerror:
        raise Exception(
            "Error while trying to get the ProjectID. Reason: '{}'".format(
                ioerror
            )
        )


def write_file(output_file_path, content):
    if output_file_path is None:
        print(content)
    else:
        try:
            with open(output_file_path, "w") as f:
                json.dump(content, f)
        except Exception as exception:
            raise Exception(
                "Error while trying to write the configuration to a file. Reason: '{}'".format(
                    exception
                )
            )


def _set_up_environment():
    if "MXRUNTIME_License.SubscriptionSecret" in os.environ:
        os.environ["MXUMS_SUBSCRIPTION_SECRET"] = os.environ[
            "MXRUNTIME_License.SubscriptionSecret"
        ]
    if "MXRUNTIME_License.LicenseServerURL" in os.environ:
        os.environ["MXUMS_LICENSESERVER_URL"] = os.environ[
            "MXRUNTIME_License.LicenseServerURL"
        ]
    if "MXRUNTIME_License.EnvironmentName" in os.environ:
        os.environ["MXUMS_ENVIRONMENT_NAME"] = os.environ[
            "MXRUNTIME_License.EnvironmentName"
        ]
    dbconfig = database.get_config()
    if dbconfig:
        os.environ[
            "MXUMS_DB_CONNECTION_URL"
        ] = "postgres://{}:{}@{}/{}".format(
            dbconfig["DatabaseUserName"],
            dbconfig["DatabasePassword"],
            dbconfig["DatabaseHost"],
            dbconfig["DatabaseName"],
        )
    project_id = _get_project_id(SIDECAR_DIR + "/" + SIDECAR_CONFIG_FILE)
    os.environ["MXUMS_PROJECT_ID"] = project_id
    e = dict(os.environ.copy())
    return e


def _is_sidecar_installed():
    if os.path.exists(SIDECAR_DIR + "/" + SIDECAR_FILENAME):
        if os.path.exists(SIDECAR_DIR + "/" + SIDECAR_CONFIG_FILE):
            return True
        else:
            logging.info("metering sidecar configuration not found")
    else:
        logging.info("metering sidecar not found")
    return False


def stage(buildpack_path, build_path, cache_dir):
    try:
        if _is_usage_metering_enabled():
            logging.info("Usage metering is enabled")
            _download(build_path, cache_dir)

            project_id = _get_project_id(
                os.path.join(build_path, "model", "metadata.json")
            )
            config = {"ProjectID": project_id}

            logging.debug("Writing metering sidecar configuration file...")
            write_file(
                os.path.join(build_path, NAMESPACE)
                + "/"
                + SIDECAR_CONFIG_FILE,
                config,
            )
        else:
            logging.info("Usage metering is NOT enabled")
    except Exception as exception:
        logging.info(
            "Encountered an exception while staging the metering sidecar. This is nothing to worry about."
        )


def run():
    try:
        if _is_usage_metering_enabled() and _is_sidecar_installed():
            logging.info("Starting metering sidecar")
            subprocess.Popen(
                SIDECAR_DIR + "/" + SIDECAR_FILENAME, env=_set_up_environment()
            )
    except Exception as exception:
        logging.info(
            "Encountered an exception while starting the metering sidecar. This is nothing to worry about."
        )
