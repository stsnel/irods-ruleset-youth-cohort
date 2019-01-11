#!/bin/bash
# \author       Niek Bats
# \file         randomCollCopy.sh
# \brief        copies random collections which matches selected wave ($2) experiment ($3) in between datefrom ($4) and datetill ($5)
#               to folder ($1) and up to amount ($6 - optional) of collections
# \copyright    Copyright (c) 2018, Utrecht University. All rights reserved
# \dependencies requires login on a rods user with execution right to this script and irods right for icommands
# \usage        bash randomCollCopy.sh <folder> <wave> <experimentType> <dateFrom> <dateTill> <(optionall) amount>

#invalid input handling

if [[ $1 = "" || $2 = "" || $3 = "" || $4 = "" || $5 = "" || $6 = "" ]] || [[ ! $7 -gt 0 && ! $7 = "" ]] ; then
#[[ ! $6 -gt 0 ]] check if = a number and more then 0
 echo "the usage of this script is: "
 echo "bash randomCollCopy.sh <folder> <howtoCopy iget-icp> <wave> <experimentType> <dateFrom> <dateTill> <(optionall) amount>"
 echo "where folder, wave, experimentType is text. dateFrom and dateTill is text in YYYY-MM-DD.HH:mm:ss format and amount is an number"
 exit 1
fi

#convert input params to named variables for readability also insta docu of what they are
folder="$1" #is text
copyHow="$2" # iget or icp => iget is default
wave="$3" #is text
experimentType="$4" #is text
dateFrom="$5" #is text in YYYY-MM-DD.HH:mm:ss format
dateTill="$6" #is text in YYYY-MM-DD.HH:mm:ss format
amount=10 #is a positive number default=10
if [[ $7 != "" ]] ; then
 amount="$7"
fi

if [[ $copyHow != "iget" && $copyHow != "icp" ]] ; then
  echo "Your copy method is not correct. It must either be  'iget' or 'icp'"
  echo "Now it is $copyHow"
  exit 1
fi

#run rule put output in an array
read -ra array <<< $(irule -F randomCollCopy.r "'$wave'" "'$experimentType'" "'$dateFrom'" "'$dateTill'")

#if array is empty give notice and exit
if [ ${#array[@]} -eq 0 ]; then
 echo "couldnt find any collections matching your parameters at the moment"
 echo "possible causes there arent any matches, the servers are down or you dont have a connection"
 exit 1
fi

echo "Selecting $amount items from: "
for item in ${array[@]}
do
 echo "$item"
done

#make folder
mkdir "$folder"
cd "$folder"

echo "selected: "
#make loop to select amount collections from array
for (( i=0; i<$amount; i++ ));
do
 #select a random collection from list
 randomNr=$(( RANDOM % ${#array[@]} ))
 #echo which one is copied and copy
 echo "${array[$randomNr]}"
 if [[ "$copyHow" == "iget" ]] ; then 
   iget -r "${array[$randomNr]}"
 fi
 if [[ "$copyHow" == "icp" ]] ; then
   icp -r "${array[$randomNr]}"
 fi
 
 #remove from list
 unset array[$randomNr]
 array=( "${array[@]}" )
done

