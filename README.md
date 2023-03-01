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

## Offline mode : Compare oversubscription strategies

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

Third, to analyse the results, launch the notebook (a jupyter notebook is pre-installed in our requirements):
```bash
jupyter notebook
```
Select `scroogevm_analysis.ipynb` and execute all cells sequentially
 
## Online mode 

More components are needed to evaluate metrics on an online configuration.

* On workers node: a probe. Please refer to its dedicated repository for installation instructions : https://github.com/jacquetpi/vmprobe
* On master node : An InfluxDB database
* On master node : Our aggregator _vmaggreg.py_ 
* (optionally) On master node : Our ballooning mechanism _vmaggreg.py_ 

> Be aware:
> - On workers node, VMs must run  on a QEMU/KVM environment with libvirt available
> - All python scripts parse environment variables for configuration. Please refer to _dotenv_ for an _.env_ example file.
> - Please note that ScroogeVM is not a scheduler and therefore cannot deploy VM by itself

With all probes running, an influxdb database at disposal and a _.env_ well configured, you can launch scroogevm live monitoring infrastucture by executing:
```bash
(master-node all) source venv/bin/activate
(master-node terminal1) python3 vmaggreg.py
(master-node terminal2) python3 scroogevm.py --strategy=greedy --debug=1 
(_optional_ master-node terminal3) python3 vmballooning.py
```

NB: debug mode is required to generate a dump file with the computed results