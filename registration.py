'''
Copyright 2021 Flexera Software LLC
See LICENSE.TXT for full license text
SPDX-License-Identifier: MIT

Author : sgeary  
Created On : Tue May 04 2021
File : registration.py
'''

import sys
import os
import stat
import logging
import argparse
import json

import CodeInsight_RESTAPIs.reports.get_reports
import CodeInsight_RESTAPIs.reports.create_report
import CodeInsight_RESTAPIs.reports.delete_report
import CodeInsight_RESTAPIs.reports.update_report

###################################################################################
# Test the version of python to make sure it's at least the version the script
# was tested on, otherwise there could be unexpected results
if sys.version_info <= (3, 5):
    raise Exception("The current version of Python is less than 3.5 which is unsupported.\n Script created/tested against python version 3.8.1. ")
else:
    pass

propertiesFile = "../server_properties.json"  # Created by installer or manually
logfileName = "_custom_report_registration.log"

###################################################################################
#  Set up logging handler to allow for different levels of logging to be capture
logging.basicConfig(format='%(asctime)s,%(msecs)-3d  %(levelname)-8s [%(filename)-25s:%(lineno)-4d]  %(message)s', datefmt='%Y-%m-%d:%H:%M:%S', filename=logfileName, filemode='w',level=logging.DEBUG)
logger = logging.getLogger(__name__)
logging.getLogger("urllib3").setLevel(logging.WARNING)  # Disable logging for requests module

#####################################################################################################
#  Code Insight System Information
#  See if there is a common file for config details
if os.path.exists(propertiesFile):
    try:
        file_ptr = open(propertiesFile, "r")
        configData = json.load(file_ptr)
        baseURL = configData["core.server.url"]
        adminAuthToken = configData["core.server.token"]
        file_ptr.close()
        logger.info("Loading config data from properties file: %s" %propertiesFile)
    except:
        logger.error("Unable to open properties file: %s" %propertiesFile)
else:
    logger.info("Using config data from create_report.py")
    baseURL = "UPDATEME" # i.e. http://localhost:8888 or https://sca.mycodeinsight.com:8443 
    adminAuthToken = "UPDATEME"

#####################################################################################################
# Quick sanity check
if adminAuthToken == "UPDATEME" or baseURL == "UPDATEME":
    logger.error("Make sure baseURL and the admin authorization token have been updated within registration.py")
    print("Make sure baseURL and the admin authorization token have been updated within registration.py")
    sys.exit()

#####################################################################################################
#  Report Details
reportName = "SPDX Report"  # What is the name to be shown within Code Insight?
enableProjectPickerValue = "false"   # true if a second project can be used within this report
reportOptions = []
reportOption = {}
reportOption["name"] = "includeChildProjects"
reportOption["label"] = "Include child project data? (True/False)"
reportOption["description"] = "Should the report include data from child projects? <b>(True/False)</b>"
reportOption["type"] = "string"
reportOption["defaultValue"] = "True"
reportOption["required"] = "true"
reportOption["order"] = "1"
reportOptions.append(reportOption)

reportOption = {}
reportOption["name"] = "includeUnassociatedFiles"
reportOption["label"] = "Include files that are not associated to inventory items? (True/False)"
reportOption["description"] = "Should the report include data for files not associated to inventory items? <b>(True/False)</b>"
reportOption["type"] = "string"
reportOption["defaultValue"] = "False"
reportOption["required"] = "true"
reportOption["order"] = "2"
reportOptions.append(reportOption)




#####################################################################################################
# Get the directory name in order to register the script
# this will be based on the git repo name is some cases
currentFolderName = os.path.basename(os.getcwd())

#####################################################################################################
# The path with the custom_report_scripts folder to called via the framework
if sys.platform.startswith('linux'):
    reportHelperScript = "create_report.sh"
elif sys.platform == "win32":
    reportHelperScript = "create_report.bat"
else:
    sys.exit("No script file for operating system")

reportPath = currentFolderName + "/" + reportHelperScript     

# Create command line argument options
parser = argparse.ArgumentParser()
parser.add_argument('-reg', "--register", action='store_true', help="Register custom reports")
parser.add_argument("-unreg", "--unregister", action='store_true', help="Unegister custom reports")
parser.add_argument("-update", "--update", action='store_true', help="Update a registered custom reports")

#----------------------------------------------------------------------#
def main():
    # See what if any arguments were provided
    args = parser.parse_args()

    if args.register and args.unregister:
        # You can use both options at the same time
        parser.print_help(sys.stderr)
    elif args.register:
        register_custom_reports()
        if sys.platform.startswith('linux'):
            # Make the shell script executable
            os.chmod(reportHelperScript, os.stat(reportHelperScript).st_mode | stat.S_IEXEC)
    elif args.unregister:
        unregister_custom_reports()
    elif args.update:
        update_custom_reports()
    else:
        parser.print_help(sys.stderr)

#-----------------------------------------------------------------------#
def register_custom_reports():
    logger.debug("Entering register_custom_reports")

    # Get the current reports so we can ensure the indexes of the new
    # reports have no conflicts
    try:
        currentReports = CodeInsight_RESTAPIs.reports.get_reports.get_all_currently_registered_reports(baseURL, adminAuthToken)
    except:
        logger.error("Unable to retrieve currently registered reports")
        print("Unable to retrieve currently registered reports.  See log file for details")
        sys.exit()

    # Determine the maximun ID of any current report
    maxReportOrder = max(currentReports, key=lambda x:x['id'])["order"]
    reportOrder = maxReportOrder + 1

    logger.info("Attempting to register %s with a report order of %s" %(reportName, reportOrder))
    print("Attempting to register %s with a report order of %s" %(reportName, reportOrder))

    try:
        reportID = CodeInsight_RESTAPIs.reports.create_report.register_report(reportName, reportPath, reportOrder, enableProjectPickerValue, reportOptions, baseURL, adminAuthToken)
        print("Report registration succeeded! %s has been registered with a report ID of %s" %(reportName, reportID))
        logger.info("Report registration succeeded! %s has been registered with a report ID of %s" %(reportName, reportID))
    except:
        logger.error("Report registration failed! Unable to registered report %s" %reportName)
        print("Report registration failed! Unable to registered report %s.  See log file for details" %reportName)
        sys.exit()


#-----------------------------------------------------------------------#
def unregister_custom_reports():
    logger.debug("Entering unregister_custom_reports")

    try:
        CodeInsight_RESTAPIs.reports.delete_report.unregister_report(baseURL, adminAuthToken, reportName)
        print("%s has been unregisted." %reportName)
        logger.info("%s has been unregisted."%reportName)
    except:
        logger.error("Unable to unregister report %s" %reportName)
        print("Unable to unregister report %s.  See log file for details" %reportName)
        sys.exit()

#-----------------------------------------------------------------------#
def update_custom_reports():
    logger.debug("Entering update_custom_reports")

    try:
        currentReportDetails = CodeInsight_RESTAPIs.reports.get_reports.get_all_currently_registered_reports_by_name(baseURL, adminAuthToken, reportName)
    except:
        logger.error("Unable to retrieve details about report: %s" %reportName)
        print("Unable to retrieve details about report: %s.  See log file for details" %reportName)
        sys.exit()

    reportID = currentReportDetails[0]["id"]
    reportOrder = currentReportDetails[0]["order"]

    logger.info("Attempting to update %s with a report id of %s" %(reportName, reportID))
    print("Attempting to update %s with a report id of %s" %(reportName, reportID))

    try:
        reportID = CodeInsight_RESTAPIs.reports.update_report.update_custom_report(reportName, reportPath, reportID, reportOrder, enableProjectPickerValue, reportOptions, baseURL, adminAuthToken)
        print("%s has been updated" %(reportName))
        logger.info("%s has been updated." %(reportName))
    except:
        logger.error("Unable to update report %s" %reportName)
        print("Unable to update report %s.  See log file for details" %reportName)
        sys.exit()
  
#----------------------------------------------------------------------#    
if __name__ == "__main__":
    main()    
