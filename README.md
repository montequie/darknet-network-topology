# Darknet Netowrk Topology

This project relate to a research work that aims to understand the network topology of the Darknet.


## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

The scripts, the DB and the TOR client described later on runs on a CentOS 7 machine (3.10.0-514.16.1.el7.x86_64)


```
$ uname -r
3.10.0-514.16.1.el7.x86_64
```

### Installing

#### Java JDK

First make sure `yum` is installed and updated
```
$ sudo yum -y update
$ sudo yum -y install wget
```
Next, download the latest Java rpm
```
$ wget --no-cookies --no-check-certificate --header "Cookie:oraclelicense=accept-securebackup-cookie" http://download.oracle.com/otn-pub/java/jdk/8u191-b12/2787e4a523244c269598db4e85c51e0c/jdk-8u191-linux-x64.rpm
```

Local install it
```
$ sudo yum -y localinstall jdk-8u191-linux-x64.rpm
```

And make sure it installed correctly
```
$ java -version
openjdk version "1.8.0_191"
OpenJDK Runtime Environment (build 1.8.0_191-b12)
OpenJDK 64-Bit Server VM (build 25.191-b12, mixed mode)
```

Next, we add the java path to the end of bash_profile file
```
$ vi ~/.bash_profile
```

The following
```
export JAVA_HOME=/usr/java/jdk1.8.0_191/
export JRE_HOME=/usr/java/jdk1.8.0_191/jre
```

and then run
```
$ source ~/.bash_profile
```

Make sure it added correctly by typing
```
$ echo $JAVA_HOME
/usr/java/jdk1.8.0_191/
```

#### Orient DB

Download the latest version of *Orient DB* and untar it
```
# wget https://s3.us-east-2.amazonaws.com/orientdb3/releases/3.0.10/orientdb-3.0.10.tar.gz -O orientdb.tar.gz
$ tar -xf orientdb.tar.gz
```

Run `server.sh` for the first time to initialize the root and give it some password - in our case lets assume the password is *Password1*.

Run the following commands to run *Orient DB* as a service

```
$ cd /home/talmoran
$ chmod +x bin/server.sh
$ sudo vi /lib/systemd/system/darkorientdb.service
```

into `darkorientdb.service` file insert
```
[Unit]
Description=dark orientdb
After=network.target

[Service]
Type=simple
# Another Type option: forking
User=root
WorkingDirectory=/home/talmoran/darknet
ExecStart='sudo /home/talmoran/bin/server.sh'
Restart=on-failure
# Other Restart options: or always, on-abort, etc

[Install]
WantedBy=multi-user.target
```

And run
```
$ sudo chmod 644 /lib/systemd/system/darkorientdb.service
$ sudo systemctl daemon-reload
$ sudo systemctl enable darkorientdb.service
$ systemctl start darkorientdb.service
```

#### TOR

Download the latest version of *tor* and install it
```
$ sudo rpm -Uvh https://dl.fedoraproject.org/pub/epel/7/x86_64/Packages/e/epel-release-7-11.noarch.rpm
$ sudo yum install tor
```

Do the following commands to configure it
```
$ cd /run
$ sudo chown root:root tor
$ sudo chmod 700 /run/tor
$ sudo vi /etc/tor/torrc
```
Insert to *torrc* file the following
```
SOCKSPort 9050
ORPort auto
BridgeRelay 1
PublishServerDescriptor 0
Exitpolicy reject *:*
ControlPort 9051
HashedControlPassword 16:27BA2A48030B11A06013BF3397A10FFF01E06B6811CA644843F1631D73
CookieAuthentication 1
```
To run the *tor* client as a service do the following
```
$ cd /home/talmoran/darknet
$ vi tor.sh
```
Insert the following to *tor.sh*
```
#!/bin/sh
sudo tor MaxCircuitDirtiness 10 MaxClientCircuitsPending 256 Bridge [<BRIDGE>IP:PORT]
```
When the [<BRIDGE>IP:PORT] is something that might change over time, you get the bridges ip and port from the following site https://bridges.torproject.org/bridges

Run the following commands to run *tor* as a service
```
$ chmod +x tor.sh
$ sudo vi /lib/systemd/system/darktor.service
```

Insert the following to *darktor.service*
```
[Unit]
Description=tor for crawl
After=network.target

[Service]
Type=simple
User=talmoran
WorkingDirectory=/home/talmoran/darknet
ExecStart=/home/talmoran/darknet/tor.sh
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

And run
```
$ sudo chmod 644 /lib/systemd/system/tor.service
$ sudo systemctl daemon-reload
$ sudo systemctl enable tor.service
$ systemctl start tor.service
```

#### Python 3.7 and PyOrient

Run the following commands to install *Python 3.7* properly, it might take couple of minutes
```
$ sudo yum install gcc openssl-devel bzip2-devel libffi libffi-devel
$ cd /root 
$ wget https://www.python.org/ftp/python/3.7.0/Python-3.7.0.tgz
$ tar xzf Python-3.7.0.tgz
$ cd Python-3.7.0
$ ./configure --enable-optimizations
$ sudo make altinstall
$ rm -f /root/Python-3.7.0.tgz
```

Now, Install *pip* and *pyorient*
```
$ pip3.7 install --upgrade pip --user
$ pip3.7 install pyorient --user
```

There is a [bug](https://github.com/orientechnologies/pyorient/issues/27#issuecomment-410819253 ":|") in *pyorient* that hasn't been solved yet in this version of *Orient DB*, so we need to make a workaround and some comments, open this file `/home/talmoran/.local/lib/python3.7/site-packages/pyorient/orient.py` and comment the following
```
if self.protocol > SUPPORTED_PROTOCOL:
            raise PyOrientWrongProtocolVersionException(
                "Protocol version " + str(self.protocol) +
                " is not supported yet by this client.", [])
```
Next, Install some more packages
```
$ pip3.7 install lxml --user
$ pip3.7 install requests --user
$ pip3.7 install -Iv PySocks==1.6.8 --user
$ pip3.7 install -Iv urllib3==1.23 --user
```
Create a working directory 
```
$ mkdir /home/talmoran/darknet
```
Upload all the *Python* and *Config* files to it
```
scp *.py talmoran@[YOURIP]]:/home/talmoran/darknet
scp *.txt talmoran@[YOURIP]:/home/talmoran/darknet
```

Install the two crawlers as services, first create two *.sh* files
```
$ cd /home/talmoran/darknet
$ vi crawl.sh
$ vi high_freq_crawl.sh
```
Insert to the files the following, respectively
```
#!/bin/sh
/usr/local/bin/python3.7 /home/talmoran/darknet/req.py
```
```
#!/bin/sh
/usr/local/bin/python3.7 /home/talmoran/darknet/high_freq.py
```

And run these commands
```
$ chmod +x crawl.sh
$ chmod +x high_freq_crawl.sh
$ sudo vi /lib/systemd/system/pycrawl.service
$ sudo vi /lib/systemd/system/highfreqcrawl.service
```

Again, Insert to the files the following, respectively
```
[Unit]
Description=crawl dark net
After=network.target

[Service]
Type=simple
User=talmoran
WorkingDirectory=/home/talmoran/darknet
ExecStart=/home/talmoran/darknet/crawl.sh
Restart=on-failure
```

```
[Unit]
Description=high freq crawl
After=network.target

[Service]
Type=simple
User=talmoran
WorkingDirectory=/home/talmoran/darknet
ExecStart=/home/talmoran/darknet/high_freq_crawl.sh
Restart=on-failure
```

And run
```
$ sudo chmod 644 /lib/systemd/system/pycrawl.service
$ sudo chmod 644 /lib/systemd/system/highfreqcrawl.service
$ sudo systemctl daemon-reload
# sudo systemctl enable pycrawl.service
# sudo systemctl enable highfreqcrawl.service
# systemctl start pycrawl.service
# sudo systemctl start highfreqcrawl.service
```


## Running the tests

Explain how to run the automated tests for this system

### Break down into end to end tests

Explain what these tests test and why

```
Give an example
```

### And coding style tests

Explain what these tests test and why

```
Give an example
```

## Deployment

Add additional notes about how to deploy this on a live system

## Built With

* [Dropwizard](http://www.dropwizard.io/1.0.2/docs/) - The web framework used
* [Maven](https://maven.apache.org/) - Dependency Management
* [ROME](https://rometools.github.io/rome/) - Used to generate RSS Feeds

## Contributing

Please read [CONTRIBUTING.md](https://gist.github.com/PurpleBooth/b24679402957c63ec426) for details on our code of conduct, and the process for submitting pull requests to us.

## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/your/project/tags). 

## Authors

* **Billie Thompson** - *Initial work* - [PurpleBooth](https://github.com/PurpleBooth)

See also the list of [contributors](https://github.com/your/project/contributors) who participated in this project.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments

* Hat tip to anyone whose code was used
* Inspiration
* etc
