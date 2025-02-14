'''
Copyright 2020 Flexera Software LLC
See LICENSE.TXT for full license text
SPDX-License-Identifier: MIT

Author : sgeary  
Created On : Wed Oct 21 2020
File : create_report.py
'''
import sys, os, logging, argparse, json, re
from datetime import datetime

import _version
import report_data
import report_artifacts
import report_errors
import common.api.project.upload_reports
import common.api.system.release
import common.report_archive


###################################################################################
# Test the version of python to make sure it's at least the version the script
# was tested on, otherwise there could be unexpected results
if sys.version_info < (3, 6):
    raise Exception("The current version of Python is less than 3.6 which is unsupported.\n Script created/tested against python version 3.6.8. ")
else:
    pass

propertiesFile = "../server_properties.json"  # Created by installer or manually
propertiesFile = logfileName = os.path.dirname(os.path.realpath(__file__)) + "/" +  propertiesFile
logfileName = os.path.dirname(os.path.realpath(__file__)) + "/_spdx_report.log"

###################################################################################
#  Set up logging handler to allow for different levels of logging to be capture
logging.basicConfig(format='%(asctime)s,%(msecs)-3d  %(levelname)-8s [%(filename)-30s:%(lineno)-4d]  %(message)s', datefmt='%Y-%m-%d:%H:%M:%S', filename=logfileName, filemode='w',level=logging.DEBUG)
logger = logging.getLogger(__name__)
logging.getLogger("urllib3").setLevel(logging.WARNING)  # Disable logging for requests module

####################################################################################
# Create command line argument options
parser = argparse.ArgumentParser()
parser.add_argument('-pid', "--projectID", help="Project ID")
parser.add_argument("-rid", "--reportID", help="Report ID")
parser.add_argument("-authToken", "--authToken", help="Code Insight Authorization Token")
parser.add_argument("-baseURL", "--baseURL", help="Code Insight Core Server Protocol/Domain Name/Port.  i.e. http://localhost:8888 or https://sca.codeinsight.com:8443")
parser.add_argument("-reportOpts", "--reportOptions", help="Options for report content")

#----------------------------------------------------------------------#
def main():

	reportName = "SPDX Report"
	reportVersion = _version.__version__

	logger.info("Creating %s - %s" %(reportName, reportVersion))
	print("Creating %s - %s" %(reportName, reportVersion))
	print("    Logfile: %s" %(logfileName))

    #####################################################################################################
    #  Code Insight System Information
    #  Pull the base URL from the same file that the installer is creating
	if os.path.exists(propertiesFile):
		try:
			file_ptr = open(propertiesFile, "r")
			configData = json.load(file_ptr)
			baseURL = configData["core.server.url"]
			file_ptr.close()
			logger.info("Using baseURL from properties file: %s" %propertiesFile)
		except:
			logger.error("Unable to open properties file: %s" %propertiesFile)

		# Is there a self signed certificate to consider?
		try:
			certificatePath = configData["core.server.certificate"]
			os.environ["REQUESTS_CA_BUNDLE"] = certificatePath
			os.environ["SSL_CERT_FILE"] = certificatePath
			logger.info("Self signed certificate added to env")
		except:
			logger.info("No self signed certificate in properties file")

	else:
		baseURL = "http://localhost:8888"   # Required if the core.server.properties files is not used
		logger.info("Using baseURL from create_report.py")

	# See what if any arguments were provided
	args = parser.parse_args()
	projectID = args.projectID
	reportID = args.reportID
	authToken = args.authToken
	reportOptions = args.reportOptions

	fileNameTimeStamp = datetime.now().strftime("%Y%m%d-%H%M%S")
	reportTimeStamp = datetime.strptime(fileNameTimeStamp, "%Y%m%d-%H%M%S").strftime("%B %d, %Y at %H:%M:%S")
	spdxTimeStamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

	# Based on how the shell pass the arguemnts clean up the options if on a linux system:w
	if sys.platform.startswith('linux'):
		reportOptions = reportOptions.replace('""', '"')[1:-1]
	
	reportOptions = json.loads(reportOptions)
	reportOptions = verifyOptions(reportOptions) 

	releaseDetails = common.api.system.release.get_release_details(baseURL, authToken)
	releaseVersion = releaseDetails["fnci.release.name"].replace(" ", "")

	logger.debug("Code Insight Release: %s" %releaseVersion)
	logger.debug("Custom Report Provided Arguments:")	
	logger.debug("    projectID:  %s" %projectID)	
	logger.debug("    reportID:   %s" %reportID)	
	logger.debug("    baseURL:  %s" %baseURL)	
	logger.debug("    reportOptions:  %s" %reportOptions)

	reportData = {}
	reportData["projectID"] = projectID
	reportData["reportName"] = reportName
	reportData["reportVersion"] = reportVersion
	reportData["reportOptions"] = reportOptions
	reportData["releaseVersion"] = releaseVersion
	reportData["fileNameTimeStamp"] = fileNameTimeStamp
	reportData["reportTimeStamp"] = reportTimeStamp
	reportData["spdxTimeStamp"] = spdxTimeStamp

	# Collect the data for the report
	
	if "errorMsg" in reportOptions.keys():

		reportFileNameBase = reportName.replace(" ", "_") + "-Creation_Error-" + fileNameTimeStamp

		reportData["errorMsg"] = reportOptions["errorMsg"]
		reportData["reportName"] = reportName
		reportData["reportFileNameBase"] = reportFileNameBase

		reports = report_errors.create_error_report(reportData)
		print("    *** ERROR  ***  Error found validating report options")
	else:
		print("    Collect data for %s" %reportName)
		reportData = report_data.gather_data_for_report(baseURL, projectID, authToken, reportData)
		print("    Report data has been collected")

		projectName = reportData["topLevelProjectName"]
		projectNameForFile = re.sub(r"[^a-zA-Z0-9]+", '-', projectName )  # Remove special characters from project name for artifacts

		# Are there child projects involved?  If so have the artifact file names reflect this fact
		if len(reportData["projectList"])==1:
			reportFileNameBase = projectNameForFile + "-" + str(projectID) + "-" + reportName.replace(" ", "_") + "-" + fileNameTimeStamp
		else:
			reportFileNameBase = projectNameForFile + "-with-children-" + str(projectID) + "-" + reportName.replace(" ", "_") + "-" + fileNameTimeStamp

		reportData["reportFileNameBase"] = reportFileNameBase

		if "errorMsg" in reportData.keys():
			reports = report_errors.create_error_report(reportData)
			print("    Error report artifacts have been created")
		else:
			reports = report_artifacts.create_report_artifacts(reportData)
			print("    Report artifacts have been created")
			for report in reports["allFormats"]:
				print("       - %s"%report)

	print("    Create report archive for upload")
	uploadZipfile = common.report_archive.create_report_zipfile(reports, reportFileNameBase)
	print("    Upload zip file creation completed")
	common.api.project.upload_reports.upload_project_report_data(baseURL, projectID, reportID, authToken, uploadZipfile)
	print("    Report uploaded to Code Insight")

	#########################################################
	# Remove the file since it has been uploaded to Code Insight
	try:
		os.remove(uploadZipfile)
	except OSError:
		logger.error("Error removing %s" %uploadZipfile)
		print("Error removing %s" %uploadZipfile)

	logger.info("Completed creating %s" %reportName)
	print("Completed creating %s" %reportName)


#----------------------------------------------------------------------# 
def verifyOptions(reportOptions):
	'''
	Expected Options for report:
		includeChildProjects - True/False
	'''
	reportOptions["errorMsg"] = []
	trueOptions = ["true", "t", "yes", "y"]
	falseOptions = ["false", "f", "no", "n"]

	includeChildProjects = reportOptions["includeChildProjects"]
	includeNonRuntimeInventory = reportOptions["includeNonRuntimeInventory"]
	includeFileDetails = reportOptions["includeFileDetails"]
	includeUnassociatedFiles = reportOptions["includeUnassociatedFiles"]
	createOtherFilesPackage = reportOptions["createOtherFilesPackage"]
	includeCopyrightsData = reportOptions["includeCopyrightsData"]

	if includeChildProjects.lower() in trueOptions:
		reportOptions["includeChildProjects"] = True
	elif includeChildProjects.lower() in falseOptions:
		reportOptions["includeChildProjects"] = False
	else:
		reportOptions["errorMsg"].append("Invalid option for including child projects: <b>%s</b>.  Valid options are <b>True/False</b>" %includeChildProjects)


	if includeNonRuntimeInventory.lower() in trueOptions:
		reportOptions["includeNonRuntimeInventory"] = True
	elif includeNonRuntimeInventory.lower() in falseOptions:
		reportOptions["includeNonRuntimeInventory"] = False
	else:
		reportOptions["errorMsg"].append("Invalid option for including Nonruntime inventory items: <b>%s</b>.  Valid options are <b>True/False</b>" %includeNonRuntimeInventory)


	if includeFileDetails.lower() in trueOptions:
		reportOptions["includeFileDetails"] = True
	elif includeFileDetails.lower() in falseOptions:
		reportOptions["includeFileDetails"] = False
	else:
		reportOptions["errorMsg"].append("Invalid option for including file details files: <b>%s</b>.  Valid options are <b>True/False</b>" %includeFileDetails)

	if includeUnassociatedFiles.lower() in trueOptions:
		reportOptions["includeUnassociatedFiles"] = True
	elif includeUnassociatedFiles.lower() in falseOptions or includeFileDetails.lower() in falseOptions:
		reportOptions["includeUnassociatedFiles"] = False
	else:
		reportOptions["errorMsg"].append("Invalid option for including unassocated files: <b>%s</b>.  Valid options are <b>True/False</b>" %includeUnassociatedFiles)

	if createOtherFilesPackage.lower() in trueOptions:
		reportOptions["createOtherFilesPackage"] = True
	elif createOtherFilesPackage.lower() in falseOptions or includeUnassociatedFiles.lower() in falseOptions:
		reportOptions["createOtherFilesPackage"] = False
	else:
		reportOptions["errorMsg"].append("Invalid option for where to map unassocated files: <b>%s</b>.  Valid options are <b>True/False</b>" %createOtherFilesPackage)

	if includeCopyrightsData.lower() in trueOptions:
		reportOptions["includeCopyrightsData"] = True
	elif includeCopyrightsData.lower() in falseOptions:
		reportOptions["includeCopyrightsData"] = False
	else:
		reportOptions["errorMsg"].append("Invalid option for including copyright projects: <b>%s</b>.  Valid options are <b>True/False</b>" %includeCopyrightsData)

	if not reportOptions["errorMsg"]:
		reportOptions.pop('errorMsg', None)

	return reportOptions

#----------------------------------------------------------------------#    
if __name__ == "__main__":
    main()  