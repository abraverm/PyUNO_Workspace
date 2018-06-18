# PyUNO Workspace

<p align="center">
    <img src="/images/workspace.png">
</p>


PyUNO Workspace is a modified version of Pyzo IDE Workspace plugin, designed for Python and PyUNO introspection. The plugin builds upon Pyzo's tried and tested interactive and introspection capabilities by making them UNO aware. This allows the developers to inspect arbitrary UNO objects in the same manner as the regular Python objects, as well as providing easy access to UNO API documentation. The final goal is to make the LibreOffice script development a seamless experience for newcomers.  

## Features

* inspect Python and PyUNO objects
* display methods with arguments description
* set arguments for methods to drill down
* iterate over UNO enumerations
* for examined objects:
  * read API Reference
  * find code examples
  * find code snippets
* generate code snippet
* and more:
  * template for macros or custom scripts

## Requirements

To get started working with PyUNO Workspace and Pyzo, you’ll need to have access to the Python 3 interpreter (not LibreOffice one). 

[Pyzo IDE](https://github.com/pyzo/pyzo) - Runs on Python3 and needs PySide/PySide2/PyQt4/PyQt5. One can install Pyzo with `python3 -m pip install pyzo`. There is [binaries](http://www.pyzo.org/start.html) for Windows, Linux and OS X and installation instructions [here](http://www.pyzo.org/install.html#install) 

## Installation and usage

Copy pyzoPyUNOWorkspace directory from this repo to INSTALL_PATH/pyzo/tools directory.

For more information see [documenation](https://github.com/kelsa-pi/PyUNO_Workspace/wiki) 

## License
BSD

## Status
Beta - Reasonably feature-complete and stable enough to be usable for day-to-day work.

