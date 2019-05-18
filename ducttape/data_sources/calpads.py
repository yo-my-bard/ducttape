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
from ducttape.exceptions import ReportNotFound
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
            self.log.info("Was unable to reach the login page. Check the browser: {}".format(self.driver_calpads.title))
            return False
        except NoSuchElementException:
            self.log.info("Was unable to reach the login page. Check the browser: {}".format(self.driver_calpads.title))
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
