# 
# Copyright (c) 2015 Tom Carroll
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
from setuptools import setup

setup(name="actuator",
      version="0.2.a1",
      description="Create models of systems in Python and then orchestrate"
                  " standing up instances of those systems",
      long_description="THIS NEEDS WRITING",
      url="https://github.com/haxsaw/actuator",
      author="Tom Carroll",
      author_email="actuator@pobox.com",
      license="MIT",
      classifiers=['Development Status :: 3 - Alpha',
                   'Environment :: Console',
                   'Environment :: OpenStack',
                   'Intended Audience :: Developers',
                   'Intended Audience :: System Administrators',
                   'Intended Audience :: Information Technology',
                   'Intended Audience :: Enterprise Architects',
                   'Topic :: Software Development :: Build Tools',
                   'Topic :: Software Development :: Libraries',
                   'Topic :: Software Development :: Libraries :: Python Modules',
                   'Topic :: System :: Installation/Setup',
                   'Operating System :: POSIX :: Linux',
                   'License :: OSI Approved :: MIT License',
                   'Programming Language :: Python :: 2',
                   'Programming Language :: Python :: 2.7'
                   ],
      keywords='cloud devops openstack ci automation orchestration modeling virtual ansible',
      packages=["actuator",
                "actuator.exec_agents",
                "actuator.exec_agents.paramiko",
                "actuator.provisioners",
                "actuator.provisioners.openstack"],
      package_dir={'': 'src'},
      install_requires=["shade",
                        "os_client_config",
                        "paramiko",
                        "ipaddress",
                        "networkx",
                        "subprocess32",
                        "fake_factory",
                        "nose",
                        "coverage",
                        "netifaces",
                        "errator"],
      )
