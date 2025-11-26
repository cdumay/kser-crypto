#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
.. codeauthor:: Cédric Dumay <cedric.dumay@gmail.com>


"""
import logging

from cdumay_error import from_exc
from cdumay_error.types import ValidationError
from cdumay_result import Result
from kser.controller import Controller
from kser_crypto.schemas import CryptoMessage

logger = logging.getLogger(__name__)


class CryptoController(Controller):
    """Controller for the crypto messages"""

    TRANSPORT = CryptoMessage

    @classmethod
    def run(cls, raw_data):
        """Controller body"""
        logger.debug("%s.ReceivedFromKafka: %s", cls.__name__, raw_data)
        try:
            kmsg = cls._onmessage(cls.TRANSPORT.loads(raw_data))
        except Exception as exc:
            error = from_exc(exc)
            logger.error(
                "%s.ImportError: Failed to load data from kafka: %s <- %s",
                cls.__name__,
                exc,
                raw_data,
                extra={"kafka_raw_data": raw_data, "error": error.to_dict()},
            )
            return Result.from_error(error)

        try:
            cls.start_processing(kmsg)
            if kmsg.entrypoint not in cls.ENTRYPOINTS:
                raise ValidationError(
                    f"Entrypoint '{kmsg.entrypoint}' not registred",
                    extra={
                        "uuid": kmsg.uuid,
                        "entrypoint": kmsg.entrypoint,
                        "allowed": list(cls.ENTRYPOINTS.keys()),
                    },
                )

            result = (
                cls.ENTRYPOINTS[kmsg.entrypoint].from_Message(kmsg).execute()
            )

        except Exception as exc:
            result = Result.from_exception(exc, kmsg.uuid)

        finally:
            cls.stop_processing()
            if result and result.retcode < 300:
                return cls._onsuccess(kmsg=kmsg, result=result)
            return cls._onerror(kmsg=kmsg, result=result)
