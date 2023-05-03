#!/bin/bash
( bash-tools/setupvm.sh vm0 1 768 stressng ; bash-tools/shutdownvm.sh vm0 ; ) &
( bash-tools/setupvm.sh vm1 1 1792 stressng ; bash-tools/shutdownvm.sh vm1 ; ) &
( bash-tools/setupvm.sh vm2 2 1792 stressng ; bash-tools/shutdownvm.sh vm2 ; ) &
( bash-tools/setupvm.sh vm3 4 3584 stressng ; bash-tools/shutdownvm.sh vm3 ; ) &
