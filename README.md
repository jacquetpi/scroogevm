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

## Offline mode

```bash
python3 scroogevm.py --strategy=greedy --load={input.json} --debug=1
```

Debug mode does two things : display progress and wrote results in a json file than can be afterward used on post-analysis

## Offline mode : Compare oversubscription strategies

One may want to compare different computation strategies on a offline setting. 
We propose traces, different strategies and a notebook to do so

Current oversubscription strategies can be seen in _model/oversubscriptioncomputation.py_

Retrieve traces from the external link and move the archive in your scroogevm directory.
Unpack with:
```bash
tar -xJf workload-traces.tar.xz
ls *.json
```

Run all three strategies on one trace:
```bash
input="decreasing-workload.json"
output_folder="results-decreasing-workload"
mkdir "$output_folder"
declare -a strategies=("percentile" "doa" "greedy")
for strategy in "${strategies[@]}"
do
    python3 scroogevm.py --strategy="$strategy" --load="$input" --debug=1
    mv dump-* "$output_folder/dump-$strategy.json"
done
ls "$output_folder"
```
NB: input and output_folder variable may be adapted to run others traces

To analyse the results, launch the notebook (a jupyter notebook is pre-installed in our requirements)
Post-analysis :
```bash
jupyter notebook
```
Select ScroogeVM analysis.ipynb and execute all cells sequentially
 
## Online mode 

More components are needed to evaluate metrics on an online configuration.

* On workers node: a probe. Please refer to its dedicated repository for installation instructions : https://github.com/jacquetpi/vmprobe
* On master node : An InfluxDB database
* On master node : Our aggregator _vmaggreg.py_ 
* (optionally) On master node : Our ballooning mechanism _vmaggreg.py_ 

> - On workers node, VMs must run  on a QEMU/KVM environment with libvirt is required
> - All python scripts parse environment variables for configuration. Please refer to _dotenv_ for an _.env_ example file.
> - Please note that ScroogeVM is not a scheduler and therefore cannot deploy VM by itself

With all probes running, an influxdb database at disposal and a _.env_ well configured : 
```bash
(master-node all) source venv/bin/activate
(master-node terminal1) python3 vmaggreg.py
(master-node terminal2) python3 scroogevm.py --strategy=greedy --debug=1 
(_optional_ master-node terminal3) python3 vmballooning.py
```