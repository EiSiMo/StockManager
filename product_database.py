import os
import re
import logging

logger = logging.getLogger("Root")


class ProductDatabase(dict):
    def __init__(self, filename, *args, **kwargs):
        super(ProductDatabase, self).__init__(*args, **kwargs)

        self.filename = filename

        logger.debug("initializing database")

        db_validation_regex = re.compile(r"^$|^(.+: (\d+, )*\d+\n)+$")

        if os.path.exists(filename):
            logger.debug(f"reading db file '{filename}'")
            with open(filename, "r", encoding="utf8") as file:
                text = file.read()
                logger.debug(f"{len(text)} characters read")
                logger.debug("testing data validity")
                if re.fullmatch(db_validation_regex, text):
                    logger.debug("data valid")
                    logger.debug("loading data")
                    for line in text.splitlines(keepends=False):
                        line = line.split(": ")
                        name = line[0]
                        codes = line[1].split(", ")
                        self.__setitem__(name, codes, save=False, log=False)
                    logger.debug("data loaded")
                    self._save()
                else:
                    logger.critical("Database file has wrong formatting")
                    raise Exception("Invalid database format")
        else:
            open(filename, "a").close()

        logger.info("database initialised")

    def __setitem__(self, name, codes, save=True, log=True):
        if log:
            logger.debug(f"__setitem__({name}, {codes}, save={save}) called")
        if isinstance(codes, str):
            codes = [codes]

        if name in self.keys():
            codes.extend(self.__getitem__(name))

        super(ProductDatabase, self).__setitem__(name, codes)

        if save:
            self._save()

    def __delitem__(self, name_or_code):
        logger.debug(f"__delitem__({name_or_code}) called")
        if name_or_code in self.keys():
            super(ProductDatabase, self).__delitem__(name_or_code)
            self._save()
        else:
            for name, codes in self.items():
                if name_or_code in codes:
                    codes.remove(name_or_code)
                    super(ProductDatabase, self).__setitem__(name, codes)
                    self._save()

    def __len__(self):
        logger.debug(f"__len__() called")
        count = 0
        for codes in self.values():
            count += len(codes)
        return count

    def _save(self):
        logger.debug(f"_save() called")
        self._sort()
        result = str()
        for name, codes in self.items():
            result += f"{name}: {', '.join(codes)}\n"

        with open(self.filename, "w", encoding="utf8") as file:
            file.write(result)

    def _sort(self):
        logger.debug("_sort() called")
        sorted_items = sorted(self.items(), key=lambda s: s[0].lower())
        self.clear()
        self.update(sorted_items)

    def find(self, code):
        logger.debug(f"find({code}) called")
        for index, (name, codes) in enumerate(self.items()):
            if code in codes:
                logger.debug(f"code '{code}' found in line {index+1}")
                return name
        logger.debug(f"code '{code}' not found in database")
        return None