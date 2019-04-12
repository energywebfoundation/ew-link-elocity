import datetime

import energyweb

from tasks.configapi import ConfigApi


class MyApp(energyweb.dispatcher.App):

    def _handle_exception(self, e: Exception):
        print(f'{e.with_traceback(e.__traceback__)}')

    def _configure(self):
        def register_config_api():
            interval = datetime.timedelta(minutes=1)
            self._register_task(ConfigApi(self.queue, interval))

        try:
            register_config_api()
        except Exception as e:
            print(f'Fatal error: {e}')
            self.loop.close()

    def _clean_up(self):
        pass


if __name__ == '__main__':
    MyApp().run()
