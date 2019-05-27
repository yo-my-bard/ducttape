import os
import pandas as pd
import numpy as np #might not need
import ast #likely don't need
import time
import datetime as dt
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import glob #might not need
import logging
import shutil
from tempfile import mkdtemp

#local import
from ducttape.webui_datasource import WebUIDataSource
from ducttape.exceptions import ReportNotFound, ReportNotReady
from ducttape.utils import (
    get_most_recent_file_in_dir,
    DriverBuilder,
    LoggingMixin
)

#Constants - sorta
EXTRACT_COLUMNS = {
    'SENR': ['RecordTypeCode', 'TransactionTypeCode', 'LocalRecordID', 'ReportingLEA', 'SchoolOfAttendance', 'SchoolOfAttendanceNPS', 'AcademicYearID',
            'SSID', 'LocalStudentID', 'StudentLegalFirstName', 'StudentLegalMiddleName', 'StudentLegalLastName', 'StudentLegalNameSuffix', 'StudentAliasFirstName',
            'StudentAliasMiddleName', 'StudentAliasLastName', 'StudentBirthDate', 'StudentGenderCode', 'StudentBirthCity', 'StudentBirthStateProvinceCode',
            'StudentBirthCountryCode', 'EnrollmentSchoolStartDate', 'EnrollmentStatusCode', 'GradeLevelCode', 'EnrollmentSchoolExitDate', 'StudentExitReasonCode',
            'StudentSchoolCompletionStatus', 'ExpectedReceiverSchoolofAttendance', 'StudentMetAllUCCSURequirementsIndicator', 'StudentSchoolTransferCode',
            'DistrictofGeographicResidence', 'StudentGoldenStateSealMeritDiplomaIndicator', 'StudentSealofBiliteracyIndicator', 'PostsecondaryTransitionStatusIndicator',
            'WorkforceReadinessStrategicSkillsCertificateProgramCompletionIndicator', 'FoodHandlerCertificationProgramCompletionIndicator',
            'PreApprenticeshipCertificationProgramCompletionIndicator', 'PreApprenticeshipProgramNonCertifiedCompletionIndicator', 'StateFederalJobProgramCompletionIndicator',
            'UploadDate', 'LastDateUpdated'],
    'SINF': ['RecordTypeCode', 'TransactionTypeCode', 'LocalRecordID', 'EffectiveStartDate', 'EffectiveEndDate', 'ReportingLEA', 'SchoolOfAttendance', 'AcademicYearID', 'SSID',
            'LocalStudentID', 'StudentLegalFirstName', 'StudentLegalMiddleName', 'StudentLegalLastName', 'StudentLegalNameSuffix', 'StudentAliasFirstName', 'StudentAliasMiddleName',
            'StudentAliasLastName', 'StudentBirthDate', 'StudentGenderCode', 'StudentBirthCity', 'StudentBirthStateProvinceCode', 'StudentBirthCountryCode',
            'StudentHispanicEthnicityIndicator', 'StudentEthnicityMissingIndicator', 'StudentRace1Code', 'StudentRace2Code', 'StudentRace3Code', 'StudentRace4Code', 'StudentRace5Code',
            'StudentRaceMissingIndicator', 'AddressLine1', 'AddressLine2', 'AddressCityName', 'AddressStateProvinceCode', 'AddressZipCode', 'StudentInitialUSSchoolEnrollmentDateK-12',
            'EnrolledinUSSchoollessthanThreeCumulativeYearsIndicator', 'ParentGuardianHighestEducationLevelCode', 'Guardian1FirstName', 'Guardian1LastName', 'Guardian2FirstName',
            'Guardian2LastName', 'UploadDate', 'LastDateUpdated'],
    'SELA': ['RecordTypeCode', 'TransactionTypeCode', 'LocalRecordID', 'ReportingLEA', 'SchoolOfAttendance', 'AcademicYearID', 'SSID',
            'StudentLegalFirstName', 'StudentLegalLastName', 'StudentBirthDate', 'StudentGenderCode', 'LocalStudentID', 'EnglishAcquisitionStatusCode',
            'EnglishAcquisitionStatusStartDate', 'PrimaryLanguageCode', 'UploadDate', 'LastDateUpdated'],
    'SPRG': ['RecordTypeCode', 'TransactionTypeCode', 'LocalRecordID', 'ReportingLEA', 'SchoolOfAttendance', 'AcademicYearID', 'SSID', 'LocalStudentID', 'StudentLegalFirstName',
            'StudentLegalLastName', 'StudentBirthDate', 'StudentGenderCode', 'EducationProgramCode', 'EducationProgramMembershipCode', 'EducationProgramMembershipStartDate',
            'EducationProgramMembershipEndDate', 'EducationServiceAcademicYear', 'EducationServiceCode', 'CaliforniaPartnershipAcademyID', 'MigrantStudentID',
            'PrimaryDisabilityCode', 'DistrictofSpecialEducationAccountability', 'HomelessDwellingTypeCode', 'UnaccompaniedYouthIndicator', 'RunawayYouthIndicator', 'Filler',
            'UploadDate', 'LastDateUpdated'],
    'CENR': ['RecordTypeCode', 'TransactionTypeCode', 'LocalRecordID', 'ReportingLEA', 'SchoolOfAttendance', 'SchoolOfAttendanceNPS', 'AcademicYearID',
            'SSID', 'LocalStudentID', 'StudentLegalFirstName', 'StudentLegalMiddleName', 'StudentLegalLastName', 'StudentLegalNameSuffix', 'StudentAliasFirstName',
            'StudentAliasMiddleName', 'StudentAliasLastName', 'StudentBirthDate', 'StudentGenderCode', 'StudentBirthCity', 'StudentBirthStateProvinceCode',
            'StudentBirthCountryCode', 'EnrollmentSchoolStartDate', 'EnrollmentStatusCode', 'GradeLevelCode', 'EnrollmentSchoolExitDate', 'StudentExitReasonCode',
            'StudentSchoolCompletionStatus', 'ExpectedReceiverSchoolofAttendance', 'StudentMetAllUCCSURequirementsIndicator', 'StudentSchoolTransferCode',
            'DistrictofGeographicResidence', 'StudentGoldenStateSealMeritDiplomaIndicator', 'StudentSealofBiliteracyIndicator', 'UploadDate', 'LastDateUpdated'],
    'DIRECTCERTIFICATION': ["Academic Year", "Reporting LEA", "School of Attendance", "Local Student ID", "SSID",
                        "Student Legal First Name", "Student Legal Middle Name", "Student Legal Last Name", "Certification Date",
                        "Certification Status"],
    'SSID': ['ReportingLEA', 'SchoolOfAttendance', 'SSID', 'LocalStudentID', 'StudentLegalLastName', 'StudentLegalFirstName', 'GenderCode',
            'StudentBirthDate', 'EnrollmentStartDate', 'GradeLevelCode', 'EnglishLanguageAcquisitionStatusCode', 'EnglishLanguageAcquisitionStatusStartDate', 'PrimaryLanguage',
            'DateSSIDCreated'],
    'SDEM': ['RecordTypeCode', 'TransactionTypeCode', 'LocalRecordID', 'EffectiveStartDate', 'EffectiveEndDate', 'ReportingLEA', 'AcademicYearID', 'SEID', 'LocalStaffID',
            'StaffLegalFirstName', 'StaffLegalMiddleName', 'StaffLegalLastName', 'StaffAliasFirstName', 'StaffAliasMiddleName', 'StaffAliasLastName', 'StaffBirthDate',
            'StaffGenderCode', 'StaffHispanicEthnicityIndicator', 'StaffEthnicityMissingIndicator', 'StaffRace1Code', 'StaffRace2Code', 'StaffRace3Code', 'StaffRace4Code',
            'StaffRace5Code', 'StaffRaceMissingIndicator', 'StaffHighestDegreeCode', 'StaffEmploymentStatusCode', 'StaffEmploymentStartDate', 'StaffEmploymentEndDate',
            'StaffServiceYearsLEA', 'StaffServiceYearsTotal', 'UploadDate', 'LastDateUpdated'],
    'SASS': ['RecordTypeCode', 'TransactionTypeCode', 'LocalRecordID', 'ReportingLEA', 'SchoolofAssignment', 'AcademicYearID', 'SEID', 'LocalStaffID', 'StaffLegalFirstName',
            'StaffLegalLastName', 'StaffBirthDate', 'StaffGenderCode', 'StaffJobClassificationCode', 'StaffJobClassificationFTEPercentage', 'NonClassroomBasedJobAssignmentCode1',
            'NonClassroomBasedJobAssignmentCode2', 'NonClassroomBasedJobAssignmentCode3', 'NonClassroomBasedJobAssignmentCode4', 'NonClassroomBasedJobAssignmentCode5',
            'NonClassroomBasedJobAssignmentCode6', 'NonClassroomBasedJobAssignmentCode7', 'UploadDate', 'LastDateUpdated'],
    'SDIS': ['RecordTypeCode', 'TransactionTypeCode', 'LocalRecordID', 'ReportingLEA', 'SchoolOfAttendance', 'AcademicYearID', 'SSID', 'LocalStudentID', 'StudentLegalFirstName',
             'StudentLegalLastName', 'StudentBirthDate', 'StudentGenderCode', 'DisciplinaryIncidentIDLocal', 'DisciplinaryIncidentOccurrenceDate', 'StudentOffenseCode',
             'IncidentMostSevereOffenseCode', 'WeaponCategoryCode', 'IncidentDisciplinaryActionTakenCode', 'DisciplinaryActionAuthorityCode', 'IncidentDisciplinaryActionDurationDays',
             'StudentInstructionalSupportIndicator', 'DisciplinaryActionModificationCategoryCode', 'RemovaltoInterimAlternativeSettingReasonCode', 'UploadDate', 'LastDateUpdated'],
    'STAS': ['RecordTypeCode', 'TransactionTypeCode', 'LocalRecordID', 'ReportingLEA', 'SchoolOfAttendance', 'AcademicYearID', 'SSID', 'LocalStudentID', 'StudentLegalFirstName',
            'StudentLegalLastName', 'StudentBirthDate', 'StudentGenderCode', 'StudentAbsenceSummaryDataCollectionExemptionIndicator', 'HourlyAttendanceSchoolTypeIndicator',
            'ExpectedAttendanceDays', 'DaysAttended', 'DaysAbsentOut-of-SchoolSuspension', 'DaysinAttendanceIn-SchoolSuspension', 'DaysAbsentExcusedNon-Suspension',
            'DaysAbsentUnexcusedNon-Suspension', 'IncompleteIndependentStudyDays', 'UploadDate', 'LastDateUpdated'],
    'CRSE': ['RecordTypeCode', 'TransactionTypeCode', 'LocalRecordID', 'ReportingLEA', 'SchoolofCourseDelivery', 'AcademicYearID', 'CRS-StateCourseCode', 'CRS-LocalCourseID',
            'CRS-CourseName', 'CRS-CourseContentCode', 'Filler', 'CRS-CTETechnicalPreparationCourseIndicator', 'CRS-UCCSUApprovedIndicator', 'CourseSectionID', 'AcademicTermCode',
            'SEID', 'LocalStaffID', 'ClassID', 'CourseSectionInstructionalLevelCode', 'EducationServiceCode', 'LanguageofInstructionCode', 'InstructionalStrategyCode',
            'IndependentStudyIndicator', 'DistanceLearningIndicator', 'MultipleTeacherCode', 'EducationProgramFundingSourceCode', 'CTECourseSectionProviderCode', 
            'UplodadDate', 'LastDateUpdated'],
    'CRSC': ['RecordTypeCode', 'TransactionTypeCode', 'LocalRecordID', 'ReportingLEA', 'SchoolofCourseDelivery', 'AcademicYearID', 'CRS-StateCourseCode', 'CRS-LocalCourseID',
            'CRS-CourseName', 'CRS-CourseContentCode', 'Filler', 'CRS-CTETechnicalPreparationCourseIndicator', 'CRS-UCCSUApprovedIndicator', 'CourseSectionID', 'AcademicTermCode',
            'SEID', 'LocalStaffID', 'ClassID', 'CourseSectionInstructionalLevelCode', 'EducationServiceCode', 'LanguageofInstructionCode', 'InstructionalStrategyCode',
            'IndependentStudyIndicator', 'DistanceLearningIndicator', 'MultipleTeacherCode', 'EducationProgramFundingSourceCode', 'CTECourseSectionProviderCode', 
            'UplodadDate', 'LastDateUpdated'],
    'SCSE': ['RecordTypeCode', 'TransactionTypeCode', 'LocalRecordID', 'ReportingLEA', 'SchoolOfAttendance', 'AcademicYearID', 'SSID', 'LocalStudentID', 'StudentLegalFirstName',
            'StudentLegalLastName', 'StudentBirthDate', 'StudentGenderCode', 'LocalCourseID', 'CourseSectionID', 'AcademicTermCode', 'StudentCreditsAttempted',
            'StudentCreditsEarned', 'StudentCourseFinalGrade', 'UC_CSUAdmissionRequirementCode', 'MarkingPeriodCode', 'UploadDate', 'LastDateUpdated'],
    'SCSC': ['RecordTypeCode', 'TransactionTypeCode', 'LocalRecordID', 'ReportingLEA', 'SchoolOfAttendance', 'AcademicYearID', 'SSID', 'LocalStudentID', 'StudentLegalFirstName',
            'StudentLegalLastName', 'StudentBirthDate', 'StudentGenderCode', 'LocalCourseID', 'CourseSectionID', 'AcademicTermCode', 'StudentCreditsAttempted',
            'StudentCreditsEarned', 'StudentCourseFinalGrade', 'UC_CSUAdmissionRequirementCode', 'MarkingPeriodCode', 'UploadDate', 'LastDateUpdated'],
    'SCTE': ['RecordTypeCode', 'TransactionTypeCode', 'LocalRecordID', 'ReportingLEA', 'SchoolOfAttendance', 'AcademicYearID', 'SSID', 'LocalStudentID', 'StudentLegalFirstName',
            'StudentLegalLastName', 'StudentBirthDate', 'StudentGenderCode', 'CTEPathwayCode', 'StudentCTEPathwayCompletionAcademicYearID', 'UploadDate', 'LastDateUpdated']
}

class Calpads(WebUIDataSource, LoggingMixin):
    """Class for interacting with the web ui of CALPADS"""

    def __init__(self, username, password, wait_time, hostname, temp_folder_path, headless=False):
        super().__init__(username, password, wait_time, hostname, temp_folder_path, headless)
        self.uri_scheme = 'https://'
        self.base_url = self.uri_scheme + self.hostname
        stream_hdlr = logging.StreamHandler()
        log_fmt = '%(asctime)s CALPADS: %(message)s'
        stream_hdlr.setFormatter(logging.Formatter(fmt=log_fmt))
        self.log.addHandler(stream_hdlr)
        self.log.setLevel(logging.INFO)

    def _login(self):
        """Logs into CALPADS"""
        self.driver.get(self.base_url)
        try:
            WebDriverWait(self.driver, self.wait_time).until(EC.presence_of_element_located((By.CLASS_NAME, 'btn-primary')))
        except TimeoutException:
            self.log.info("Was unable to reach the login page. Check the browser: {}".format(self.driver.title))
            return False
        except NoSuchElementException:
            self.log.info("Was unable to reach the login page. Check the browser: {}".format(self.driver.title))
            return False
        user = self.driver.find_element_by_id("Username")
        user.send_keys(self.username)
        pw = self.driver.find_element_by_id("Password")
        pw.send_keys(self.password)
        agreement = self.driver.find_element_by_id("AgreementConfirmed")
        self.driver.execute_script("arguments[0].click();", agreement)
        btn = self.driver.find_element_by_class_name('btn-primary') 
        btn.click()
        try:
            WebDriverWait(self.driver, self.wait_time).until(EC.presence_of_element_located((By.ID, 'org-select')))
        except TimeoutException:
            self.log.info('Something went wrong with the login. Checking to see if there was an expected error message.')
            try:
                #TODO: Use id, tag-name, or class for the alert if I remember the next time it happens
                alert = WebDriverWait(self.driver, self.wait_time).until(EC.presence_of_element_located((By.XPATH, '/html/body/div[3]/div/form/div[1]')))
                if 'alert' in alert.get_attribute('class'):
                    self.log.info("Found an expected alert during login: '{}'".format(self.driver.find_element_by_xpath('/html/body/div[3]/div/form/div[1]/div/ul/li').text))
                    return False
                else:
                    self.log.info('There was an unexpected message during login. See driver.')
                    return False
            except TimeoutException:
                self.log.info('There was an unexpected error during login. See driver.')
                return False

        return True

    def download_url_report(self, report_url, temp_folder_name):
        """CALPADS does not have stateful reports"""
        raise NotImplementedError("CALPADS does not have stateful reports.")

    def _select_lea(self, lea_code):
         """
         Factored out common process for switching to a different LEA in the dropdown
         
         Args:
         lea_code (str): string of the seven digit number found next to your LEA name in the org select menu. For most LEAs,
         this is the CD part of the County-District-School (CDS) code. For independently reporting charters, it's the S.
         """
         select = Select(self.driver.find_element_by_id('org-select'))
         for opt in select.options:
             if lea_code in opt.text:
                 opt.click()
                 break
         #Wait for site to re-load if it registered a change in LEA
         WebDriverWait(self.driver, self.wait_time).until(EC.element_to_be_clickable((By.ID, 'org-select')))

    def _rename_a_calpads_download(self, folder_path, new_file_text):
        """Gets most recent file in the object's calpads folder and renames it with new_file_text with timestamp appended"""

        recent_file = get_most_recent_file_in_dir(folder_path)
        file_ext = os.path.splitext(recent_file)[1]
        new_file = folder_path + "/" + str(new_file_text) + " " + str(dt.datetime.now().strftime('%Y-%m-%d %H_%M_%S')) + file_ext
        os.rename(recent_file, new_file)

    def get_current_language_data(self, ssid, second_chance=False):
        """
        Search for SSID's latest language data and return the table as a dataframe.

        Get the current language data in CALPADS for the provided SSID. Helpful when
        updating the student information system when receiving a new student.
        Returns a dataframe. When using in a Jupyter notebook, use display() instead of
        print() for checking the language data values in a prettier format.

        Args:
        ssid: CALPADS state student identifier. Can be either a string or integer format.
        second_chance: used during recursion to try again if the wrong table is found.

        Returns:
        language_data (DataFrame): The SELA language information on a CALPADS student profile or raise ReportNotFound exception if it fails
        """
        self.driver = DriverBuilder().get_driver(headless=self.headless)
        self._login()

        ssid_search = self.driver.find_element_by_id('inputSSID')
        ssid_search.send_keys(ssid)

        ssid_btn = self.driver.find_element_by_id('btnSearchSSIDLeftNav')
        ssid_btn.click()
        #Wait for SELA Grid to be clickable
        elem = WebDriverWait(self.driver, self.wait_time).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="StudentDetailsPanelBar"]/li[4]/a')))
        elem.click() #open up the SELA Grid
        try:
            WebDriverWait(self.driver, self.wait_time).until(EC.visibility_of_element_located((By.ID, 'SELAGrid')))
        except TimeoutException:
            #Maybe the click didn't work the first time, try clicking again
            self.driver.find_element_by_xpath('//*[@id="StudentDetailsPanelBar"]/li[4]/a').click()
            WebDriverWait(self.driver, self.wait_time).until(EC.visibility_of_element_located((By.ID, 'SELAGrid')))
        
        try:
            WebDriverWait(self.driver, self.wait_time).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="SELAGrid"]/table/tbody'))) #waiting for the table to load
        except TimeoutException:
            #If the table body is never in the DOM, but the table header exists, it could just mean the SSID doesn't have data.
            if self.driver.find_element_by_xpath('//*[@id="SELAGrid"]/table'): #If the header of the table exists...
                lang_data = pd.read_html(self.driver.page_source)[1]
                try:
                    assert all(lang_data.columns == ['Unnamed: 0', 'Reporting LEA', 'Acquisition Code', 'Status Date', 'Primary Language Code',
                                            'Correction Reason Code','Effective Start Date'])
                except AssertionError:
                    self.log.info('Found a table, but it was the wrong one it seems. Trying again')
                    self.get_current_language_data(ssid, True)
                except ValueError: #the assert comparison fails if the array lengths aren't the same
                    self.log.info('Found a table, but it was the wrong one it seems. Trying again')
                    self.get_current_language_data(ssid, True)
                else:
                    #Passed the validations/checks, return the dataframe
                    self.log.info("Student {} does not appear to have any language data. Once confirmed, student should get tested.".format(ssid))
                    self.driver.close()
                    return lang_data
            else:
                self.log.info('Something unexpected happened when trying to load the SELA table for {}'.format(ssid))
                self.driver.close() #TODO: Should the driver always close at this point?
                raise ReportNotFound #TODO: A more explicit/accurate error might be helpful
        
        #If the table body *is* found in the DOM, do the following:
        lang_data = pd.read_html(self.driver.page_source)[1] #TODO: Index error happened? Might be going too fast?
        if not second_chance:
            try:
                assert all(lang_data.columns == ['Unnamed: 0', 'Reporting LEA', 'Acquisition Code', 'Status Date', 'Primary Language Code',
                                            'Correction Reason Code','Effective Start Date'])
            except AssertionError:
                self.log.info('Found a table, but it was the wrong one it seems. Trying again')
                self.get_current_language_data(ssid, True)
            except ValueError: #the assert comparison fails if the array lengths aren't the same
                self.log.info('Found a table, but it was the wrong one it seems. Trying again')
                self.get_current_language_data(ssid, True)
            else:
                if len(lang_data) != 0:
                    self.log.info(
                        'Found the latest language data for {}: Status: {}, Status Date: {}, Primary Lang: {}.'.format(
                            ssid, lang_data['Acquisition Code'][0], lang_data['Status Date'][0], lang_data['Primary Language Code'][0]
                            )
                        )
                    self.driver.close()
                    return lang_data
                else:
                    self.log.info('Student {} does not appear to have any language data. Once confirmed, student should get tested.'.format(ssid))
                self.driver.close()
                return lang_data
        else: #Sometimes the wrong tab is clicked and the wrong table is indexed at 1. #TODO: Add a max_attempts to get it right feature - this issue seems dependent on loading issues
            try:
                assert all(lang_data.columns == ['Unnamed: 0', 'Reporting LEA', 'Acquisition Code', 'Status Date', 'Primary Language Code',
                                            'Correction Reason Code','Effective Start Date'])
            except AssertionError:
                self.log.info('Found the wrong table again. Closing the driver.')
                self.driver.close()
                raise ReportNotFound #TODO: A more explicit/accurate error might be helpful
            else:
                if len(lang_data) != 0:
                    self.log.info(
                        'Found the latest language data for {}: Status: {}, Status Date: {}, Primary Lang: {}.'.format(
                            ssid, lang_data['Acquisition Code'][0], lang_data['Status Date'][0], lang_data['Primary Language Code'][0]
                            )
                        )
                    self.driver.close()
                    return lang_data
                else:
                    self.log.info('Student {} does not appear to have any language data. Once confirmed, student should get tested.'.format(ssid))
                self.driver.close()
                return lang_data
    
    def request_extract(self, lea_code, extract_name, active_students=None, academic_year=None, adjusted_enroll=None,
                        active_staff=True, employment_start_date=None, employment_end_date=None, effective_start_date=None,
                        effective_end_date=None):
        """
        Request an extract with the extract_name from CALPADS.
        
        For Direct Certification Extract, pass in extract_name='DirectCertification'. For SSID Request Extract, pass in 'SSID'.
        For the others, use their abbreviated acronym, e.g. SENR, SELA, etc.
        
        Args:
        lea_code (str): string of the seven digit number found next to your LEA name in the org select menu. For most LEAs,\
            this is the CD part of the County-District-School (CDS) code. For independently reporting charters, it's the S.
        extract_name (str): For Direct Certification Extract, pass in extract_name='DirectCertification'. For SSID Request Extract, pass in 'SSID'.\
            For the others, use their abbreviated acronym, e.g. SENR, SELA, etc. Spelling matters, capitalization does not.
        active_students (bool): Optional. When using SPRG, True checks off Active Student in the form. When True, extract pulls only student programs \
            with a NULL exit date for the program at the time of the request.
        academic_year (str): String in the format YYYY-YYYY. Required only for some extracts.
        adjusted_enroll (bool): Adjusted cumulative enrollment. When True, pulls students with enrollments dates that fall in the typical school year.\
            When False, it pulls students with enrollments from July to June (7/1/YYYY - 6/30/YYYZ). Optional and used only for CENR.
        active_staff (bool): Optional. For SDEM - only extract SDEM records of active staff. Default to True. If False, must provide employment\
            date range.
        employment_start_date (str): Optional. For SDEM - input used to filter Staff members from the extract. Suggested Format: MM/DD/YYYY.
        employment_end_date (str): Optional. For SDEM - input used to filter Staff members from the extract. Suggested Format: MM/DD/YYYY.
        effective_start_date (str): Optional. For SDEM, the effective start date of the SDEM record - input used to filter Staff members from\
            the extract. Suggested Format: MM/DD/YYYY.
        effective_end_date (str): Optional. For SDEM, the effective end date of the SDEM record - input used to filter Staff members from\
            the extract. Suggested Format: MM/DD/YYYY.
        temp_folder_name (str): the name for a sub-directory in which the files from the browser will be stored. If this directory does not exist,\
            it will be created. The parent directory will be the temp_folder_path used when setting up Calpads object. If None, a temporary directory\
            will be created and deleted as part of cleanup.
        max_attempts (int): the max number of times to try checking for the download. There's a 1 minute wait between each attempt.
        pandas_read_csv_kwargs: additional arguments to pass to Pandas read_csv

        Returns:
        Boolean: True if extract request was successful
        """
        #already changed to appropriate LEA
        extract_name = extract_name.upper()

        #Some validations of required Args
        if extract_name in ['CENR', 'SCSC']:
            assert academic_year, "For {} Extract, academic_year is required. Format YYYY-YYYY".format(extract_name)

        #navigate to extract page
        if extract_name == 'SSID':
            self.driver.get('https://www.calpads.org/Extract/SSIDExtract')
        elif extract_name == 'DIRECTCERTIFICATION':
            self.driver.get('https://www.calpads.org/Extract/DirectCertificationExtract')
        else:
            self.driver.get('https://www.calpads.org/Extract/ODSExtract?RecordType={}'.format(extract_name))
        
        #confirm that we made it to a valid request extract page
        try:
            #Check that we made it to a page with a "Request File" button
            if extract_name != 'SPRG':
                WebDriverWait(self.driver, self.wait_time).until(EC.text_to_be_present_in_element((By.CLASS_NAME, 'btn-primary'), 'Request File'))
            else:
                #Currently, SPRG page has a btn-secondary class. Could change later and break the code. ¯\_(ツ)_/¯ 
                WebDriverWait(self.driver, self.wait_time).until(EC.text_to_be_present_in_element((By.CLASS_NAME, 'btn-secondary'), 'Request File'))
        except TimeoutException:
            self.log.info("The requested extract, {}, is not a supported extract name.".format(extract_name))
            raise ReportNotFound
        
        #Select the schools (generally move all) TODO: Consider supporting selective school selection
        if extract_name != 'SDEM':
            self.__move_all_for_extract_request()

        #Need specific method handlers for the extracts. Dispatch to form handlers
        form_handlers = {
            'SSID': lambda: self.__fill_ssid_request_extract(lea_code),
            'DIRECTCERTIFICATION': lambda: self.__fill_dc_request_extract(),
            'SENR': lambda: self.__fill_senr_request_extract(),
            'SELA': lambda: self.__fill_sela_request_extract(),
            'SPRG': lambda: self.__fill_sprg_request_extract(active_students),
            'CENR': lambda: self.__fill_cenr_request_extract(academic_year, adjusted_enroll),
            'SINF': lambda: self.__fill_sinf_request_extract(),
            'CRSC': lambda: self.__fill_crsc_request_extract(academic_year),
            'CRSE': lambda: self.__fill_crse_request_extract(academic_year),
            'SASS': lambda: self.__fill_sass_request_extract(academic_year),
            'SDEM': lambda: self.__fill_sdem_request_extract(active_staff, employment_start_date, employment_end_date,
                                                            effective_start_date, effective_end_date),
            'STAS': lambda: self.__fill_stas_request_extract(academic_year),
            'SCTE': lambda: self.__fill_scte_request_extract(academic_year),
            'SCSC': lambda: self.__fill_scsc_request_extract(academic_year),
            'SCSE': lambda: self.__fill_scse_request_extract(academic_year),
            'SDIS': lambda: self.__fill_sdis_request_extract(academic_year),
        }
        #Call the handler
        form_handlers[extract_name]()

        #Click request button
        if extract_name != 'SPRG':
            req = self.driver.find_element_by_class_name('btn-primary')
        else:
            #Currently, SPRG page has a btn-secondary class.
            req = self.driver.find_element_by_class_name('btn-secondary')
        req.click()
        try:
            WebDriverWait(self.driver, self.wait_time).until(EC.visibility_of_element_located((By.CLASS_NAME, 'alert-success')))
        except TimeoutException:
            self.log.info("The extract request was unsuccessful.")
            self.driver.close()
            return False
        
        self.log.info("{} {} Extract Request made successfully. Please check back later for download".format(lea_code, extract_name))
        self.driver.get("https://www.calpads.org")

        return True

    def __move_all_for_extract_request(self):
        """Refactored method to click move all in request extract forms"""
        #Defaults to the first moveall button which is generally what we want. TODO: Consider supporting other extract request methods. e.g. date range, etc.
        #moveall = self.driver.find_elements_by_class_name('moveall')[0]
        time.sleep(2) #TODO: Don't think there's something explicit to wait for here, the execution seems to be going too fast causes errors on SCSC
        select = Select(self.driver.find_element_by_id('bootstrap-duallistbox-nonselected-list_School'))
        static_options = len(select.options)
        n = 0
        #Going to click moveall multiple times, but I think the time.sleep() above actually solves the need for this.
        while n < static_options:
            moveall = self.driver.find_elements_by_class_name('moveall')[0]
            moveall.click()
            n += 1
        assert Select(self.driver.find_element_by_id('bootstrap-duallistbox-nonselected-list_School')).options.__len__() == 0, "Failed to select all of the school options"
        #TODO: Confirm that we don't need to wait for anything here.

    def __fill_ssid_request_extract(self, lea_code):
        """Messiest extract request handler. Assumes that a recent SENR file has been fully Posted for the SSID extract to be current."""
        #We're going back to FileSubmission because we need the job ID for the latest file upload.
        self.driver.get('https://www.calpads.org/FileSubmission')
        try:
            WebDriverWait(self.driver, self.wait_time).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="FileSubmissionSearchResults"]/table')))
            jid = self.driver.find_element_by_xpath('//*[@id="FileSubmissionSearchResults"]/table/tbody/tr[1]/td[2]').text            
        except NoSuchElementException:
            self.driver.get('https://www.calpads.org/FileSubmission/')
            self.driver.refresh()
            WebDriverWait(self.driver, self.wait_time).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="FileSubmissionSearchResults"]/table')))
        finally:
            jid = self.driver.find_element_by_xpath('//*[@id="FileSubmissionSearchResults"]/table/tbody/tr[1]/td[2]').text
        #make sure the first row is what is expected
        assert self.driver.find_element_by_xpath('//*[@id="FileSubmissionSearchResults"]/table/tbody/tr[1]/td[6]').text == 'SSID-Enrollment',  "Found a job ID, but it doesn't look like it's for an SSID extract."

        #navigate to extract page
        self.driver.get('https://www.calpads.org/Extract/SSIDExtract')

        try:
            jobid_option = WebDriverWait(self.driver, self.wait_time).until(EC.element_located_selection_state_to_be((By.XPATH,'//*[@id="SelectedJobIDssidExtractbyJob"]/option'), True))
        except TimeoutException:
            self.log.info('Job ID failed to automatically populate for SSID Extract for {}. Did you post the file you uploaded yet?'.format(lea_code))
            raise ReportNotReady
        else:
            WebDriverWait(self.driver, self.wait_time).until(EC.element_located_selection_state_to_be((By.XPATH,'//*[@id="SelectedJobIDssidExtractbyJob"]/option'), True))
            select = Select(self.driver.find_element_by_id('SelectedJobIDssidExtractbyJob'))
            #Find the element that's been pre-selected
        for opt in select.all_selected_options: #TODO: this returned stale element once for some reason...
            self.driver.execute_script("arguments[0].removeAttribute('selected')", opt)
            #TODO: Confirm if this needs a wait, sometimes throws errors here            
        for opt in select.options:
            if opt.get_attribute('value') == jid:
                self.driver.execute_script("arguments[0].setAttribute('selected', 'selected')", opt)
            else:
                continue
        
        self.__move_all_for_extract_request()
        #Defaulting to all grades TODO: Maybe support specific grades? Doubt it'd be useful.
        all_grades = Select(self.driver.find_element_by_id('GradeLevel'))
        all_grades.select_by_visible_text('All')
        
    def __fill_sprg_request_extract(self, active_students):
        """Handler for SPRG Extract Request form. Mostly just for selecting all programs in the required field.
        Args:
        active_students (bool): when True, extract only pulls students without an exit date in the program. i.e. have NULL exit dates.
        """
        #Check off Active Students
        if active_students:
            elem = self.driver.find_element_by_id('ActiveStudentsprgAcdmcYear')
            elem.click()
            #TODO: Confirm no need to wait
        
        #Select programs - defaulting to All TODO: Support specific programs.
        select = Select(self.driver.find_element_by_id('EducationProgramCodesprgAcdmcYear'))
        select.select_by_value("All")
        #TODO: Confirm no need to wait

    def __fill_dc_request_extract(self):
        """Handler for Direct Certification Extract request form. Currently only supports default values at loading."""
        pass
    
    def __fill_sinf_request_extract(self):
        """Handler for SINF Extract request form. Currently only supports default values at loading."""
        pass
    
    def __fill_sela_request_extract(self):
        """Handler for SELA Extract request form. Currently only supports default values at loading."""
        pass
    
    def __fill_senr_request_extract(self):
        """Handler for SENR Extract request form. Currently only supports default values at loading."""
        pass
    
    def __fill_crsc_request_extract(self, academic_year):
        """Handler for CRSC Extract request form."""
        if academic_year:
            year = self.driver.find_element_by_name('AcademicYear_input')
            year.clear()
            year.send_keys(academic_year)
    
    def __fill_crse_request_extract(self, academic_year):
        """Handler for CRSE Extract request form."""
        if academic_year:
            year = self.driver.find_element_by_name('AcademicYear_input')
            year.clear()
            year.send_keys(academic_year)
    
    def __fill_sass_request_extract(self, academic_year):
        """Handler for SASS Extract request form."""
        if academic_year:
            year = self.driver.find_element_by_name('AcademicYear_input')
            year.clear()
            year.send_keys(academic_year)
    
    def __fill_stas_request_extract(self, academic_year):
        """Handler for STAS Extract request form."""
        if academic_year:
            year = self.driver.find_element_by_name('AcademicYear_input')
            year.clear()
            year.send_keys(academic_year)
    
    def __fill_scte_request_extract(self, academic_year):
        """Handler for SCTE Extract request form."""
        if academic_year:
            year = self.driver.find_element_by_name('AcademicYear_input')
            year.clear()
            year.send_keys(academic_year)
    
    def __fill_scsc_request_extract(self, academic_year):
        """Handler for SCSC Extract request form."""
        if academic_year:
            year = self.driver.find_element_by_name('AcademicYear_input')
            year.clear()
            year.send_keys(academic_year)

    def __fill_scse_request_extract(self, academic_year):
        """Handler for SCSE Extract request form."""
        if academic_year:
            year = self.driver.find_element_by_name('AcademicYear_input')
            year.clear()
            year.send_keys(academic_year)
    
    def __fill_sdis_request_extract(self, academic_year):
        """Handler for SDIS Extract request form."""
        if academic_year:
            year = self.driver.find_element_by_name('AcademicYear_input')
            year.clear()
            year.send_keys(academic_year)
    
    def __fill_sdem_request_extract(self, active_staff, employment_start_date, employment_end_date, effective_start_date, effective_end_date):
        """Handler for SDEM Extract request form."""
        if active_staff:
            self.driver.find_element_by_id('ActiveStaff').click()
        else:
            #Must provide employment date range if not selecting active staff
            assert (employment_start_date is not None) and (employment_end_date is not None), "If active_staff is not True, employment start and end date must be provided."
        if employment_start_date:
            self.driver.find_element_by_id('EmploymentStartDate').send_keys(employment_start_date)
        if employment_end_date:
            self.driver.find_element_by_id('EmploymentEndDate').send_keys(employment_end_date)
        if effective_start_date:
            self.driver.find_element_by_id('EffectiveStartDate').send_keys(effective_start_date)
        if effective_end_date:
            self.driver.find_element_by_id('EffectiveEndDate').send_keys(effective_end_date)

    def __fill_cenr_request_extract(self, academic_year, adjusted_enroll):
        """Handler for CENR Extract request form.
        Args:
        adjusted_enroll (bool): Adjusted cumulative enrollment. When True, pulls students with enrollments dates that fall in the typical school year.\
            When False, it pulls students with enrollments from July to June (7/1/YYYY - 6/30/YYYZ)
        academic_year (str): a string in the format, YYYY-YYYY, e.g. 2018-2019.
        """
        #Defaulting to all grades TODO: Maybe support specific grades? Doubt it'd be useful.
        all_grades = Select(self.driver.find_element_by_id('GradeLevel'))
        all_grades.select_by_visible_text('All')

        #Academic year
        year = self.driver.find_element_by_name('AcademicYear_input')
        year.clear()
        year.send_keys(academic_year)

    def download_extract(self, lea_code, extract_name, active_students=None, academic_year=None, adjusted_enroll=None,
                        active_staff=True, employment_start_date=None, employment_end_date=None, effective_start_date=None,
                        effective_end_date=None, temp_folder_name=None, max_attempts=10, pandas_read_csv_kwargs={}):
        """
        Request an extract with the extract_name from CALPADS.
        
        For Direct Certification Extract, pass in extract_name='DirectCertification'. For SSID Request Extract, pass in 'SSID'.
        For the others, use their abbreviated acronym, e.g. SENR, SELA, etc.
        
        Args:
        lea_code (str): string of the seven digit number found next to your LEA name in the org select menu. For most LEAs,\
            this is the CD part of the County-District-School (CDS) code. For independently reporting charters, it's the S.
        extract_name (str): For Direct Certification Extract, pass in extract_name='DirectCertification'. For SSID Request Extract, pass in 'SSID'.\
            For the others, use their abbreviated acronym, e.g. SENR, SELA, etc. Spelling matters, capitalization does not.
        temp_folder_name (str): the name for a sub-directory in which the files from the browser will be stored. If this directory does not exist,\
            it will be created. The parent directory will be the temp_folder_path used when setting up Calpads object. If None, a temporary directory\
            will be created and deleted as part of cleanup.
        max_attempts (int): the max number of times to try checking for the download. There's a 1 minute wait between each attempt.
        pandas_read_csv_kwargs: additional arguments to pass to Pandas read_csv

        Returns:
        DataFrame: A Pandas DataFrame of the extract
        """
        #TODO: Consider designing differently- currently both requesting and downloading LEA are done one at a time. You
        #can dramatically reduce amount of time needed to wait by requesting for several LEAs and then downloading.
        #Should API encourage direct request_extract usage?
        extract_name = extract_name.upper()

        if temp_folder_name:
            extract_download_folder_path = self.temp_folder_path + '/' + temp_folder_name
            os.makedirs(extract_download_folder_path, exist_ok=True)
        else:
            extract_download_folder_path = mkdtemp(dir=self.temp_folder_path)

        self.driver = DriverBuilder().get_driver(download_location=extract_download_folder_path, headless=self.headless)
        self._login()
        self._select_lea(lea_code)

        self.driver.get("https://www.calpads.org/Extract")
        WebDriverWait(self.driver, self.wait_time).until(EC.element_to_be_clickable((By.ID, 'org-select')))
        
        attempt = 0
        success = False
        today_ymd = dt.datetime.now().strftime('%Y-%m-%d')
        #TODO: Confirm these extract names
        expected_extract_types = {
            'SENR': "SSID Enrollment ODS Download",
            'SINF': "Student Information ODS Download",
            'SPRG': "Student Program ODS Download",
            'SELA': "Student English Language Acquisition Status ODS Download",
            'DIRECTCERTIFICATION': 'Direct Certification',
            'SSID': 'SSID Extract',
            'CENR': 'Cumulative Enrollment ODS Download',
            'SASS': 'Staff Assignment ODS Download',
            'SDEM': 'Staff Demographics ODS Download',
            'STAS': 'Student Absence Summary ODS Download',
            'SDIS': 'Student Discipline ODS Download',
            'CRSE': 'Course Section Enrollment ODS Download',
            'CRSC': 'Course Section Completion ODS Download',
            'SCSE': 'Student Course Section Enrollment ODS Download',
            'SCSC': 'Student Course Section Completion ODS Download',
            'SCTE': 'Student Career Technical Education ODS Download', 
            }
        
        while attempt < max_attempts and not success:
            try:
                WebDriverWait(self.driver, self.wait_time).until(EC.visibility_of_element_located((By.XPATH, '//*[@id="ExtractRequestGrid"]/table/tbody/tr[1]/td[3]')))
            except TimeoutException:
                raise Exception('The extract table took too long to load. Adjust the wait_time variable.')
            else:
                extract_type = self.driver.find_element_by_xpath('//*[@id="ExtractRequestGrid"]/table/tbody/tr[1]/td[3]').text
                extract_status = self.driver.find_element_by_xpath('//*[@id="ExtractRequestGrid"]/table/tbody/tr[1]/td[5]').text #expecting Complete
                date_requested = dt.datetime.strptime(self.driver.find_element_by_xpath('//*[@id="ExtractRequestGrid"]/table/tbody/tr[1]/td[7]').text,
                                                "%m/%d/%Y %I:%M %p").date().strftime('%Y-%m-%d') #parse the text datetime on CALPADS, extract the date, format it to match today variable formatting
            
            if extract_type == expected_extract_types[extract_name] and extract_status == "Complete" and date_requested == today_ymd: 
                current_file_num = list(os.walk(extract_download_folder_path))[0][2]
                dlbutton = self.driver.find_element_by_xpath('//*[@id="ExtractRequestGrid"]/table/tbody/tr[1]/td[1]/a') #Select first download button
                dlbutton.click()
                wait_for_new_file_in_folder(extract_download_folder_path, current_file_num)
                success = True
            else:
                attempt += 1
                self.log.info("The download doesn't seem ready during attempt #{} for LEA {}".format(attempt, lea_code))
                time.sleep(60) #We do want a full minute wait
                self.driver.refresh()
                WebDriverWait(self.driver, self.wait_time).until(EC.element_to_be_clickable((By.ID, 'org-select')))
        
        if not success:
            self.driver.close()
            self.log.info("All download attempts failed for {}. Cancelling {} extract download. Make sure you've requested the extract today.".format(lea_code, extract_name))
            raise ReportNotFound
        
        #Set a default variable for names:
        if 'names' not in pandas_read_csv_kwargs.keys():
            #If no column names are passed into pandas, use the default file layout names.
            kwargs_copy = pandas_read_csv_kwargs.copy()
            kwargs_copy['names'] = EXTRACT_COLUMNS[extract_name]
        extract_df = pd.read_csv(get_most_recent_file_in_dir(extract_download_folder_path), sep='^', header=None, **kwargs_copy)
        self.log.info("{} {} Extract downloaded.".format(lea_code, extract_name))
        self.driver.close()

        #Download won't have an easily recognizable name. Rename.
        #TODO: Unless one memorizes the LEA codes, should consider optionally supporting a text substitution of the lea_code via a dictionary.
        self._rename_a_calpads_download(extract_download_folder_path, new_file_text=lea_code + " " + extract_name + " Extract")

        if not temp_folder_name:
            shutil.rmtree(extract_download_folder_path)

        return extract_df

def wait_for_new_file_in_folder(folder_path, num_files_original, max_attempts=20000):
    """ Waits until a new file shows up in a folder.
    """
    file_added = False
    attempts = 0
    #TODO Wait based on time passed, not number of loops?
    while True and attempts < max_attempts:
        for root, folders, files in os.walk(folder_path):
            # break 'for' loop if files found
            if len(files) > len(num_files_original):
                    file_added = True
                    break
            else:
                continue
        # break 'while' loop if files found
        if file_added:
            # wait for download to complete fully after it's been added - hopefully 3 seconds is enough.
            time.sleep(3)
            return True
        attempts +=1
    return False