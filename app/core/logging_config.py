import logging


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,#info及以上会显示，即debug细节不会反映
        format="%(asctime)s %(levelname)s %(name)s %(message)s"
        #format：用格式字符串，包含时间、等级、模块名、日志内容。对应占位符是 %(asctime)s、`%(levelname)s`、`%(name)s`、`%(message)s`。
    )
