# SmartScheduler daemon for init.d

This project contain the SmartScheduler daemon for running cloud optimisation strategies in background as Linux service. 

## Prerequisites

Python3 should be installed and used. This project is developed and rested on Python3.5 . You also need python **setuptools** (example: yum install python34-setuptools).

## Installing the library
### Using Setup.py
We need sudo in order to create /etc/smartscheduler directory for default configuration:

```bash
$ sudo python3 setup.py install
```

After successful installation it is important to write a configuration file for the library. For more information see SmartScheduler library.

### Using pip3
```bash
pip3 install smartsched.daemon
```
The same requirements to configuration is applied to your installation so dont forget to create it.

## How to use daemon

After successful installation you can start and stop daemon using **service** command:
```bash
service smart_daemon start
service smart_daemon stop
service smart_daemon restart
```

## How to use strategies

Strategy is a python script with special variable *target_class*. This variable should point to class which inherit from *smartsched.daemon.base_strategy.BaseStrategy*. In order to do something the class should redefine *perform_strategy* method: this method called by daemon every *sleep_time* seconds. You can define path to your *strategy_path* and *sleep_time* in smartsched configuration.

# For Developers

## Development version installation
In order to install the packet for development you just need to clone the git project and install with pip locally with [dev] extantion:

```bash
pip3 install -e .[dev]
```

It will install all necessary libraries which you will use for versioning and release publishing.

## How to increment version
The following versioning schema is chosen for the project: `project_name-<Major>.<minor>.<patch>`
In order to simplify the process of version incrementing the *bumpversion* utility is used. The detailed documentation here: https://github.com/peritus/bumpversion

Examples:
```sh
bumpversion patch
bumpversion minor
bumpversion major
```

In order to simplify the process of making new patch the .patch_it.sh script have been introduced. If you run it the new patch is created, new tag is created, all commits uploads to the master, all tags uploads to the master. Be careful if the fail happened during git interaction, it means that new version was released but not uploaded to git and if you run the full patch script again, ***it will make new release again***.

# How to build and upload
Depending on your version of OS and Python3 you will have two ways of uploading wheel packet to the PyPi.org . Despite this fact, first of all you need to create wheel of your project:

```bash
python3 setup.py bdist_wheel
```

When the `smartsched-<M.m.p>-py3-none-any.whl` created in you *dist* directory you can upload it to the PyPi. Either:
```bash
twine upload dist/smartsched-<M.m.p>-py3-none-any.whl
```
or:
```bash
python3 setup.py bdist_wheel upload
```

## Code style example

We try to folow PEP-8 standard during the development. The following example could be a useful hint:

```python
import standard1
import standard2

import third_party
from third_party import bar
from third_party.spec import baz
from third_party.bar import Quux


from app_specific import ar

GLOBAL_CONSTANT = "Constant"


class SampleClass:
    """Summary of class here.

    Longer class information....
    Longer class information....

    Attributes:
        first_parameter: responsible for ...
        second_parameter: responsible for ...
    """

    def __init__(self, first_arg, second_arg):
        # TODO(your@mail.com: todo example.
        # TODO(IgorPelevanyuk): assigney name .
        pass

    def _private_helper_method(self):

        pass

    def public_method(self, first_arg, second_arg):
        """General method description.

        Detailed description of current method.

        Args(If necessary add description):
            first_arg: alowed values
            second_arg: purpose

        Returns(If may be unclear):
            {'key1': value1,
             'key2': value2,
             'key3': [list_value1, list_value2, ...]}

        Raises(If necessary):
            CustomError: if custom error occured

        """
        any_variable = None
        result = standard1.long_function(first_arg, second_arg,
                                         any_variable)
        return result

    def another_public_method(self):

        just_var = GLOBAL_CONSTANT
        return just_var


# If file is a script use "check if main"
def main():
    pass

if __name__ == '__main__':
    main()
```
