from selenium import webdriver
from npwd.core import UrlInfo, Handler

class EastMoney(Handler):
    name = 'east_money'

    def __init__(self, url: UrlInfo, driver: webdriver.Chrome):
        self.url = url
        self.driver = driver
        super().__init__(url, driver)
    
    def handler(self):
        # WebDriverWait(self.driver, timeout=10)
        # self.driver.execute_script('tk_tg_zoomin()')
        js = """
            setTimeout(() => {
                document.querySelectorAll('div').forEach(e => {
                    if (e.style.zIndex >= 100) {
                        e.style.display = 'none';
                    }
                });
            }, 1000);
        """
        self.driver.execute_script(js)
        super().handler()
