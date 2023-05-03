#!/bin/bash
sudo firewall-cmd --reload
bash-tools/setupvmnat.sh vm0 stressng 11000 ; 
bash-tools/setupvmnat.sh vm1 stressng 11001 ; 
bash-tools/setupvmnat.sh vm2 stressng 11002 ; 
bash-tools/setupvmnat.sh vm3 stressng 11003 ; 
sudo firewall-cmd --direct --add-rule ipv4 nat POSTROUTING 0 -j MASQUERADE
sudo firewall-cmd --direct --add-rule ipv4 filter FORWARD 0 -d 0.0.0.0/0 -j ACCEPT
