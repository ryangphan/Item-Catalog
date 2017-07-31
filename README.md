# PROJECT 4: Item Catalog

### by Ryan Phan

Project Item Catalog is a part of the [Udacity Full Stack Web Developer Nanodegree](https://www.udacity.com/course/full-stack-web-developer-nanodegree--nd004).

The project consist of the following files:
  - database_setup.py : the python file to setup the database for this project
  - lotsofmenus.py : contains information that is going to be added to the database
  - project.py : the python file contains the source code of this project
  - README.md : guideline to run this project

Skills used for this project:
  - python
  - HTML
  - CSS
  - Bootstrap
  - Flask
  - SQLAlchemy
  - OAuth
  - Google/Facebook login

### Installation

To run this project, you will need to successfully install these following software:
  - [Python 3](https://www.python.org/downloads/)
  - [Vagrant](https://www.vagrantup.com/)
  - [VirtualBox](https://www.virtualbox.org/)

Additionally, you need to have these files as well:
  - Download or clone this [repository](https://github.com/udacity/fullstack-nanodegree-vm)

### How To Run This Project

  - Download and install Python3, and VirtualBox
  - Open the terminal on your computer and direct it to vagrant sub-directory inside the udacity-fullstack-vm folder
  - Installing Vagrant in the previous folder by using the following command
  ```sh
  $ vagrant up
  ```
  - It will took a while to install the virtual machine base on the speed of your internet.
  - After successfully installing the virtual machine, you can log in by using the command
  ```sh
  $ vagrant ssh
  ```
  - Redirect your virtual machine's vagrant folder to the project folder by using command:
  ```sh
  $ cd /vagrant
  $ cd catalog
  ```
  - To setup the database, please use the following command:
  ```sh
  python database_setup.py
  ```
  - To load the database, please use the following command:
  ```sh
  python lotsofmenus.py
  ```
  - Finally, to run the project, please use the following command:
  ```sh
  python project.py
  ```

### Miscellaneous
- This README document is based on a template suggested by PhilipCoach in this Udacity forum [post](https://discussions.udacity.com/t/readme-files-in-project-1/23524/2)
- The code of this project is based on a repository of Udacity, which is intended to be used as supplement course material. The original code can be founded [here](https://github.com/udacity/ud330)
