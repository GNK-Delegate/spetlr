# This script submits a run to databricks to execute the complete test-suite
# as a prerequisite, the library under test should already be built
# This script does a the following things in order:
#  - creates a unique test area on the databricks file system (dbfs)
#  - clean the entire tests folder and copies it to dbfs
#  - copies the library to the test area
#  - submits a job run to databricks that
#    - installs the library from the test area
#    - executes a main file that
#      - discovers unittests and executes them within the current python interpreter
#        (only the current interpreter carries references to the spark runtime.
#        calling subprocesses does not work.)
#      - writes all test stdout to a log file in the test area once finished.
#  - once the job is submitted, all job details are written to a json file
#    The details json file can be used to fetch the job result with the fetch_test_job script

param (
# to submit parallel runs, you must specify this parameter
  [Parameter(Mandatory=$false)]
  [ValidateNotNullOrEmpty()]
  [string]
  $testJobDetails= "test_job_details.json",

# in the atc pipeline we wish to test with multiple versions.
  [Parameter(Mandatory=$false)]
  [ValidateNotNullOrEmpty()]
  [string]
  $sparkVersion = "9.1.x-scala2.12"

)

$srcDir = "$PSScriptRoot/../.."


# start time of this script for job details
$now = (Get-Date -Format yyyy-MM-ddTHH.mm)



# import utility functions
. "$PSScriptRoot\..\deploy\Utilities\all.ps1"
. "$PSScriptRoot\spark-dependencies.ps1"


# for separating tasks, we will do everything in our own dir (allows parallel jobs):
$testguid = "$([guid]::NewGuid())"
$testDir = "dbfs:/test/$([guid]::NewGuid())"
dbfs mkdirs $testDir

# discover libraries in the dist folder
[array]$libs = Get-ChildItem -Path dist -Filter *.whl | ForEach-Object -Member name
Write-Host "To be installed on cluster: $($libs -join ", ")"
[array]$sparkWheels =  $libs | ForEach-Object -Process {@{whl = "$testDir/dist/$_"}}

# upload the library
dbfs cp -r --overwrite  "$srcDir/dist" "$testDir/dist"

# upload the test main file
dbfs cp --overwrite  "$PSScriptRoot/main.py" "$testDir/main.py"


# next step is to upload all unittests
Push-Location -Path $srcDir

pip install pyclean
pyclean tests # remove *.pyc and __pycache__
# upload all tests
dbfs cp --overwrite -r tests/ "$testDir/tests"

Pop-Location

# remote path of the log
$logOut = "$testDir/results.log"

# construct the run submission configuration
$run = @{
    run_name = "Testing Run"
    # single node cluster is sufficient
    new_cluster= @{
        spark_version=$sparkVersion
        spark_conf= @{
            "spark.databricks.cluster.profile"= "singleNode"
            "spark.master"= "local[*, 4]"
            "spark.databricks.delta.preview.enabled"= $true
            "spark.databricks.io.cache.enabled"= $true
        }
        azure_attributes=${
                "availability"= "ON_DEMAND_AZURE",
                "first_on_demand": 1,
                "spot_bid_max_price": -1
            }
        node_type_id= "Standard_DS3_v2"
        custom_tags =@{
          ResourceClass="SingleNode"
        }
        spark_env_vars= @{
            PYSPARK_PYTHON= "/databricks/python3/bin/python3"
        }
        cluster_log_conf= @{
            dbfs=@{
                destination="$testDir/cluster-logs"
            }
        }
        num_workers= 0
    }
    # in addition to standard dependencies, install the libs that we just uploaded
    libraries= $spark_dependencies + $sparkWheels

    # This scripts runs the test suite
    spark_python_task= @{
      python_file="$testDir/main.py"
      parameters=@(
        # running in the spark python interpreter, the python __file__ variable does not
        # work. Hence, we need to tell the script where the test area is.
        "--basedir=$testDir",
        # we can actually run any part of out test suite, but some files need the full repo.
        # Only run tests from this folder.
        "--folder=tests/cluster"
      )
    }
  }
# databricks runs submit actually has an option to pass the json on the command line.
# But here we need to do this with a json file because the json string is pretty funky and it breaks otherwise
Set-Content "$srcDir/run.json" ($run | ConvertTo-Json -Depth 4)
# submit the run and save the ID
$runId = (databricks runs submit --json-file "$srcDir/run.json" | ConvertFrom-Json).run_id
Remove-Item "$srcDir/run.json"

# report on status
Write-Host "============================================================================"
Write-Host "Started Run with ID $runId"
Write-Host "Using test dir $testDir"

$run = (databricks runs get --run-id $runId | ConvertFrom-Json)
Write-Host "Run url: $($run.run_page_url)"

# Roll the test details. When testing locally, this makes it easier to recover old runs.
if(Test-Path -Path $testJobDetails -PathType Leaf){
    $old_job_details = Get-Content $testJobDetails | ConvertFrom-Json
    $new_filename = "$(Split-Path -LeafBase $testJobDetails).$($old_job_details.submissionTime).json"
    $parent = Split-Path -Parent $testJobDetails
    if ($parent){
        $new_filename = Join-Path -Path $parent -ChildPath $new_filename
    }
    Set-Content "$new_filename" ($old_job_details | ConvertTo-Json -Depth 4)
    Write-Host "Previous details at $testJobDetails were moved to $new_filename."
}

# write the test details file
$job_details = @{
    runId=$runId
    testDir=$testDir
    submissionTime=$now
    testFolder=$testFolder
    environmentType= $environmentType
    environmentName=$environmentName
    logOut=$logOut
}
Set-Content "$testJobDetails" ($job_details | ConvertTo-Json -Depth 4)

Write-Host "test job details written to $testJobDetails"
Write-Host "you can now use fetch_test_job.ps1 to check and collect the result of your test run."
Write-Host "============================================================================"

