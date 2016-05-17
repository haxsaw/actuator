"""
Simple test program for clouds.yml file of os_client_config

Run this from the same directory as your clouds.yml file; it will use that file's contents to
attempt to authenticate to the cloud and then get a list of flavors the cloud supports that is named as the
first argument to the program on the command line. If it can't connect, an exception is printed out, otherwise
the list of flavors is printed. Note that on citycloud, the default, this can take some time.
"""
from pprint import pprint
import sys

import shade
import os_client_config

if __name__ == "__main__":
    if len(sys.argv) == 1:
        cname = "citycloud"
    else:
        cname = sys.argv[1]
    config = os_client_config.OpenStackConfig().get_one_cloud(cname)
    print config.name, config.region, config.config
    cloud = shade.OpenStackCloud(cloud_config=config)

    try:
        images = cloud.list_flavors()
    except Exception as e:
        print("OH NOES!")
        pprint(e)
    else:
        pprint(images)
