import os
import pandas as pd
import numpy as np
import ast
import time
import datetime as dt
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import glob
import logging

#local import
from ducttape.webui_datasource import WebUIDataSource
from ducttape.exceptions import ReportNotFound, ReportNotReady
from ducttape.utils import (
    get_most_recent_file_in_dir,
    DriverBuilder,
    LoggingMixin
)

class Calpads(WebUIDataSource, LoggingMixin):
    """Class for interacting with the web ui of CALPADS"""

    def __init__(self, username, password, wait_time, hostname, temp_folder_path, headless=False):
        super().__init__(username, password, wait_time, hostname, temp_folder_path, headless)
        self.uri_scheme = 'https://'
        self.base_url = self.uri_scheme + self.hostname

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
        #TODO: Has to be implemented because of metaclass, should we explicitly throw NotImplementedError?
        pass

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

        self.driver.find_element_by_xpath('//*[@id="StudentDetailsPanelBar"]/li[4]/a').click() #open up the SELA Grid
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
                self.log.info("Student {} does not appear to have any language data. Once confirmed, student should get tested.".format(ssid))
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
                    self.log.info('Found the latest language data for {}: Status: {}, Status Date: {}, Primary Lang: {}.'.format(ssid, lang_data['Acquisition Code'][0], lang_data['Status Date'][0], lang_data['Primary Language Code'][0]))
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
                    self.log.info('Found the latest language data for {}: Status: {}, Status Date: {}, Primary Lang: {}.'.format(ssid, lang_data['Acquisition Code'][0], lang_data['Status Date'][0], lang_data['Primary Language Code'][0]))
                else:
                    self.log.info('Student {} does not appear to have any language data. Once confirmed, student should get tested.'.format(ssid))
                self.driver.close()
                return lang_data
    
    def _request_extract(self, lea_code, extract_name, active_students=None, academic_year=None, adjusted_enroll=None):
        """
        Request the extract from CALPADS.
        
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

        Returns:
        bool: True for a successful extract request
        """
        #already changed to appropriate LEA
        extract_name = extract_name.upper()

        #Some validations of required Args
        if extract_name in ['CENR']:
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
        self.__move_all_for_extract_request()

        #Dispatch to form handlers
        form_handlers = {
            'SSID': lambda: self.__fill_ssid_request_extract(lea_code),
            'DIRECTCERTIFICATION': lambda: self.__fill_dc_request_extract(),
            'SENR': lambda: self.__fill_senr_request_extract(),
            'SELA': lambda: self.__fill_sela_request_extract(),
            'SPRG': lambda: self.__fill_sprg_request_extract(active_students),
            'CENR': lambda: self.__fill_cenr_request_extract(academic_year, adjusted_enroll),
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
        WebDriverWait(self.driver, self.wait_time).until(EC.visibility_of_element_located((By.CLASS_NAME, 'alert-success')))
        
        self.log.info("{} {} Extract Request made successfully. Please check back later for download".format(lea_code, extract_name))
        self.driver.get("https://www.calpads.org")

        return True

    #Expecting to need specific method handlers for the extracts. e.g. _request_senr_extract, _request_ssid_extract
    def __move_all_for_extract_request(self):
        """Refactored method to click move all in request extract forms"""
        #Defaults to the first moveall button which is generally what we want. TODO: Consider supporting other extract request methods. e.g. date range, etc.
        moveall = self.driver.find_element_by_class_name('moveall')
        moveall.click()
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
    
    def __fill_sela_request_extract(self):
        """Handler for SELA Extract request form. Currently only supports default values at loading."""
        pass
    
    def __fill_senr_request_extract(self):
        """Handler for SENR Extract request form. Currently only supports default values at loading."""
        pass

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
        year = Select(self.driver.find_element_by_id('AcademicYear'))
        year.select_by_visible_text(academic_year)


    def download_extract(self, extract_name, max_attempts=10):
        """This is what users are expected to call"""
        #Call request extract
        #Handle download
        pass