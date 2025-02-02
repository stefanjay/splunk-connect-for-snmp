#
# Copyright 2021 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os

import yaml

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)
PROFILES_GET_RETRIES = 3


def load_profiles():
    active_profiles = {}
    pkg_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "profiles"
    )
    for file in os.listdir(pkg_path):
        if file.endswith("yaml"):
            with open(os.path.join(pkg_path, file), encoding="utf-8") as of:
                profiles = yaml.safe_load(of)
                logger.info(
                    f"loading {len(profiles.keys())} profiles from shared profile group {file}"
                )
                for key, profile in profiles.items():
                    active_profiles[key] = profile
    try:
        with open(CONFIG_PATH, encoding="utf-8") as file:
            config_runtime = yaml.safe_load(file)
            if "profiles" in config_runtime:
                profiles = config_runtime.get("profiles", {})
                logger.info(
                    f"loading {len(profiles.keys())} profiles from runtime profile group"
                )
                for key, profile in profiles.items():
                    if key in active_profiles:
                        if not profile.get("enabled", True):
                            logger.info(f"disabling profile {key}")
                            del active_profiles[key]
                        else:
                            active_profiles[key] = profile
                    else:
                        active_profiles[key] = profile
    except FileNotFoundError:
        logger.info(f"File: {CONFIG_PATH} not found")

    return active_profiles


class ProfilesManager:
    def __init__(self, mongo):
        self.mongo = mongo
        self.profiles_coll = mongo.sc4snmp.profiles

    def gather_profiles(self):
        active_profiles = {}

        pkg_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "profiles"
        )
        for file in os.listdir(pkg_path):
            if file.endswith("yaml"):
                with open(os.path.join(pkg_path, file), encoding="utf-8") as of:
                    profiles = yaml.safe_load(of)
                    logger.info(
                        f"loading {len(profiles.keys())} profiles from shared profile group {file}"
                    )
                    for key, profile in profiles.items():
                        active_profiles[key] = profile

        try:
            with open(CONFIG_PATH, encoding="utf-8") as file:
                config_runtime = yaml.safe_load(file)
                if "profiles" in config_runtime:
                    profiles = config_runtime.get("profiles", {})
                    logger.info(
                        f"loading {len(profiles.keys())} profiles from runtime profile group"
                    )
                    for key, profile in profiles.items():
                        if key in active_profiles:
                            if not profile.get("enabled", True):
                                logger.info(f"disabling profile {key}")
                                del active_profiles[key]
                            else:
                                active_profiles[key] = profile
                        else:
                            active_profiles[key] = profile
        except FileNotFoundError:
            logger.info(f"File: {CONFIG_PATH} not found")
        return active_profiles

    def update_profiles(self, profiles):
        profiles_to_insert = []
        for key, value in profiles.items():
            profiles_to_insert.append({key: value})
        with self.mongo.start_session() as session:
            with session.start_transaction():
                self.profiles_coll.delete_many({})
                self.profiles_coll.insert_many(profiles_to_insert)

    def update_all_profiles(self):
        all_profiles = self.gather_profiles()
        self.update_profiles(all_profiles)

    def return_all_profiles(self):
        for retry in range(3):
            profiles = self.request_profiles()
            if profiles:
                return profiles
        return {}

    def request_profiles(self):
        profiles = {}
        profiles_cursor = self.profiles_coll.find({}, {"_id": 0})
        for item in profiles_cursor:
            profiles.update(item)
        return profiles
