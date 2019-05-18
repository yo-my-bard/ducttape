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
from ducttape.utils import (
    get_most_recent_file_in_dir,
    configure_selenium_chrome,
    LoggingMixin
)

class Calpads(WebUIDataSource, LoggingMixin):
    """Class for interacting with the web ui of CALPADS"""

    def __init__(username, password, wait_time, hostname, temp_folder_path, headless=False):
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
