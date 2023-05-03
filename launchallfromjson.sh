#!/bin/bash
if (( "$#" != "2" )) 
then
  echo "Missing argument : ./launchallfromjson.sh input.json output_folder"
  exit -1
fi
input="$1"
if [ ! -f "$input" ]; then
    echo "Error: json input does not exist : $input"
    exit -1
fi
output_folder="$2"
if [ -d "$output_folder" ]; then
    echo "Error: output directory already exists, a non-existing directory is required : $output_folder"
    exit -1
fi
mkdir "$output_folder"
source venv/bin/activate
declare -a strategies=("percentile" "doa" "nsigma" "rclike" "borg" "maxpeak" "greedy")
for strategy in "${strategies[@]}"
do
    echo "Running ScroogeVM on $strategy strategy"
    python3 scroogevm.py --strategy="$strategy" --load="$input" --debug=1
    mv -v dump-*.json "$output_folder/dump-$strategy.json"
    mv dump-lstm.csv "$output_folder/dump-lstm.csv"
done
ls "$output_folder"