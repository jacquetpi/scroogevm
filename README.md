# ScroogeVM

ScroogeVM is an oversubscription estimator. It allows cloud scheduler (such as OpenStack) to judge how much resources can be considered as free on each node for new deployments, ending up to dynamically allow more virtual resources than physically available.

## How It Works

ScroogeVM divides time through windows (called scope) of an arbitrary length.
At the end of each scope, it computes node usage ratio based on percentile and node stability.

ScroogeVM can operate in online or offline mode. On online mode, it fetchs data from an influxDB database. On offline mode, values are retrieved from a json file to enhance portability. 

## Setup

```bash
apt-get update && apt-get install -y git python3 python3.venv
git clone https://github.com/jacquetpi/scroogevm
cd scroogevm/
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Offline mode execution (Compare oversubscription strategies based on dataset)

One may want to compare different computation strategies on a offline setting. 
We propose traces, a selection of strategies, and a notebook to do so.

First, retrieve our archive from the external link, move it to the `scroogevm` directory and unpack traces with :
```bash
tar -xJf workload-traces.tar.xz
ls *.json
```

Second, execute ScroogeVM on one of the traces with different strategies.  
Three are available : percentile, doa and greedy (the latest being the computation introduced in our approach).   
Implementation can be seen in _model/oversubscriptioncomputation.py_

From the `scroogevm` directory, run all three strategies on one trace with the following script:
```bash
input="decreasing-workload.json"
output_folder="results-decreasing-workload"
./launchallfromjson.sh "$input" "$output_folder"
```
`input` represents one of the json files obtained from our archive.  
`output_folder` will be a directory used to store obtained results. Specified location is later needed for the notebook analysis.  
NB: It is a time consuming step (can take more than 1 hour)

Third, to analyse the results, launch the notebook (a jupyter notebook is pre-installed in our requirements):
```bash
jupyter notebook
```
Select `scroogevm_analysis.ipynb` and execute all cells sequentially
 
## Online mode : Setup complements

More components are needed to evaluate metrics on an online configuration.  

> Be aware:
> - On workers node, VMs must run on a QEMU/KVM environment with libvirt available
> - All python scripts parse environment variables for configuration. Please refer to _dotenv_ for an _.env_ example file.
> - Please note that ScroogeVM is not a scheduler and therefore cannot deploy VM by itself

To start online setup :
```bash
sudo mkdir /var/lib/scroogevm/
sudo chown -R $(id -u):$(id -g) /var/lib/scroogevm/
cp dotenv .env
```

#### 1) Probe
**On each worker node**, a probe and its exporter are required. Please refer to its dedicated repository for installation instructions: https://github.com/jacquetpi/vmprobe  

* Prefix used during vmprobe installation should be written on `.env` file (on `AGGREG_STUB_LIST` key). If multiple workers are used, all prefix should be written to the file.
* A prometheus http endpoint (e.g. `http://192.168.0.1:9100/metrics`) should be accessible from scroogevm point of view and written on `.env` file (on `AGGREG_STUB_LIST` key).. If multiple workers are used, all url should be written to the file.

#### 2) InfluxDB
**On master node**, a database is required. ScroogeVM was developed using a 2.x InfluxDB database.
To quickly setup an environment, we provide a bash script launching InfluxDB as a container while persisting data on volume.

```bash
(master-node) misc/influxdb.sh
```

To setup this environment, connect to `http://localhost:8086` using a web brower.  
Click `Get started` and register a `user`, an `organisation` and a `bucket` name. All three should be written on `.env` file.  
Select `Configure later` and generate a token by clicking on `Data > Tokens > Generate Token > Read/Write Token`  
Select `Scoped > your_bucket_name` on `read` and `write`, validate,  and copy paste its value (by clicking its name) to your `.env` file

#### 3) ScroogeVM

**On master node**, ScroogeVM is required. It uses prometheus URL as unique identifier of worker nodes.

On `.env` file, list workers node URLs on `SCHED_NODES` parameter. Others can be let on default.

`SCHED_SCOPE_SLICE_S` and `SCHED_SCOPE_S` should be let to an identical value. This value can however be reduced to quickly test if current setup is working (as computations are only done at the end of each scope). On default 5s probe fetch time, do not go below 20s.

#### 4) Optional : VMballooning

**On master node**, VMBallooning is optional. It is a naive VM memory oversubscription mechanism based on ballooning.

Monitoring is performed from the same influxdb database used for ScroogeVM. 
However, a libvirt access to each worker is also required to adapt VM configuration.  
A certificate-based access to each worker is therefore required.

```bash
(master-node) ssh-copy-id worker1-user@worker1-ip
(master-node) virsh -c 'qemu+ssh://worker1-user@worker1-ip/system?keyfile=id_rsa' list
```

If the latest command worked, remote libvirt management is possible. This should be repeated for each node.  
Be aware of the `system` keyword in the URL that may be replaced by `session` if you use default qemu URI on worker.  
For the `LIBVIRT_NODES` parameter in `.env` file, register all `qemu+ssh` URL used for your workers as a key:value format where the key is the prometheus worker URL (refer to the example format).

## Online mode : Execution

With all probes running, an influxdb database at disposal and a _.env_ well configured, you can launch scroogevm live monitoring infrastucture by executing:
```bash
(master-node all) source venv/bin/activate
(master-node terminal1) python3 vmaggreg.py
(master-node terminal2) python3 scroogevm.py --strategy=greedy --debug=1 
(_optional_ master-node terminal3) python3 vmballooning.py
```

NB: debug mode is required to generate a dump file with the computed results
