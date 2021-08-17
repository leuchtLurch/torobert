# -*- coding: utf-8 -*-

from imapclient import IMAPClient, SEEN
from torolib import torolib
import logging
import email
import email.header
import html2text
import queue
import ssl

class textGenerator(object):

    def __init__(self, redis):
        self.log = logging.getLogger(__name__)
        self.log.info('initializing textGenerator extension ' + __loader__.name)
        self.torolib = torolib(redis = redis)
        self.config = self.torolib.getJsonContent(fileName=f'/etc/torobert/{__loader__.name}.config.json')
        self.texts = self.torolib.getTextsFromExcel(f'/etc/torobert/{__loader__.name}.texts.xlsx')
        self.textIndices = self.torolib.getTextIndices(self.texts)
        self.mails = queue.Queue()
        self.imap = self.imapConnect()
        #loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
        logging.getLogger('imapclient.imaplib').disabled=True

    def cleanup(self):
        '''closes the imap connection'''
        self.log.info('cleanup for textGenerator extension ' + __loader__.name)
        if self.imap:
            self.imap.logout()


    def decode_mime_words(self,s):
        '''converts mail headers/subject lines like "=?utf-8?Q?Subject?=" to usable text'''
        return u''.join(word.decode(encoding or 'utf8') if isinstance(word, bytes) else word for word, encoding in email.header.decode_header(s))


    def fetchMails(self):
        '''opens toroberts mail account and does reads mails'''
        self.log.debug('fetchMails called')
        if 'imapclient.imapclient.IMAPClient' in str(type(self.imap)):
            try:
                self.imap.select_folder(self.config['folder'])
            except:
                self.log.debug('getMails, problems while reading imap folder, trying to reconnect to the server')
                self.imapConnect()
                try:
                    self.imap.select_folder(self.config['folder'])
                except:
                    self.log.error('getMails, unable to access mail folder')
                    self.imap = False
            if self.imap:
                messages = self.imap.search(['UNSEEN', 'NOT', 'DELETED'])
                #messages = self.imap.fetch(messages, ['ENVELOPE','RFC822.PEEK[]','BODY.PEEK[TEXT]']) # thanks to PEEK the message is not yet marked as seen
                messages = self.imap.fetch(messages, ['ENVELOPE','RFC822','BODY.PEEK[TEXT]']) # thanks to PEEK the message is not yet marked as seen
                for messageId, data in messages.items():
                    envelope = data[b'ENVELOPE']
                    #email_msg = email.message_from_bytes(data[b'RFC822[]'])
                    email_msg = email.message_from_bytes(data[b'RFC822'])
                    if email_msg.is_multipart():
                        mailbodyPlaintext = ''
                        mailbodyHTML = ''
                        for part in email_msg.walk():
                            if part.get_content_type() == "text/plain":
                                mailbodyPlaintext = part.get_payload(decode=True) #to control automatic email-style MIME decoding (e.g., Base64, uuencode, quoted-printable)
                            elif part.get_content_type() == "text/html":
                                mailbodyHTML = part.get_payload(decode=True) #to control automatic email-style MIME decoding (e.g., Base64, uuencode, quoted-printable)
                        if mailbodyPlaintext != '':
                            mailbody = mailbodyPlaintext
                        else:
                            mailbody = mailbodyHTML
                    else:
                        mailbody = email_msg.get_payload(decode=True)
                    try:
                        mailbody = mailbody.decode()
                    except UnicodeDecodeError:
                        try:
                            mailbody = mailbody.decode('iso-8859-1')
                        except:
                            self.log.error('getMails: Error while decoding the mail')
                    mailbody = html2text.html2text(mailbody)
                    # commit mail to queue if its sender is not on the senderBlockList
                    senderAddress = envelope.from_[0].mailbox.decode() + "@" + envelope.from_[0].host.decode()
                    senderInBlocklist = False
                    for sender in self.config.get('senderBlockList',[]):
                        if sender in senderAddress:
                            senderInBlocklist = True
                    if not senderInBlocklist:
                        self.mails.put({'messageId':messageId,'from':envelope.from_[0].name.decode(),'date':envelope.date,'subject':self.decode_mime_words(envelope.subject.decode()),'text':mailbody})
                        self.log.info(f'reading mail, from={envelope.from_[0].name.decode()} aka. {senderAddress}, date={envelope.date}')
                    else:
                        self.log.info(f'not reading mail because of senderBlockList, from={envelope.from_[0].name.decode()} aka. {senderAddress}, date={envelope.date}')
                self.log.info(f'found {self.mails.qsize()} unread mails')


    def getMessageOnRecurrence(self, variables={}, calledBy=''):
        logging.info('getMessageOnRecurrence was called')
        result = False
        if self.mails.qsize() == 0:
            self.fetchMails()
        if self.mails.qsize() > 0:
            mail = self.mails.get()
            if self.mails.qsize() == 1:
                addon = self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['oneMoreMail'], variables=variables).get('text','')
            elif self.mails.qsize() > 1:
                variables['NUMBEROFMAILS'] = self.mails.qsize()
                addon = self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['multipleMoreMails'], variables=variables).get('text','')
            else:
                addon = self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['noMoreMail'], variables=variables).get('text','')
            variables['MAILFROM'] = mail["from"]
            variables['MAILSUBJECT'] = mail["subject"]
            variables['MAILSUFFIX'] = addon
            prefix = self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['mailPrefix'], variables=variables).get('text','')
            suffix = self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['mailSuffix'], variables=variables).get('text','')
            result = {'text':prefix + " " + mail["text"].strip() + " " + suffix,'prio':2}
            self.imap.add_flags(mail['messageId'], [SEEN])
        elif calledBy=='webApp':
            result =  self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['noMailsAvailable'], variables=variables)
        return result


    def getWebAppConfig(self):
        '''returns a dict which tells torobert how to make this textGenerator configurable through the dynamic configuration website'''
        result = { \
            'onDemand': 1, \
            'heading': 'Mails', \
            'fontAwesomeIcon': 'fas fa-envelope', \
        }
        return result


    def imapConnect(self):
        '''establishes a connection to the configured imap server'''
        result = False
        self.log.debug('imapConnect called')
        ssl_context = ssl.create_default_context()
        # don't check if certificate hostname doesn't match target hostname
        ssl_context.check_hostname = False
        # don't check if the certificate is trusted by a certificate authority
        ssl_context.verify_mode = ssl.CERT_NONE
        try:
            result = IMAPClient(host=self.config['imapServer'], ssl_context=ssl_context)
        except:
            self.log.error('connectMail, error connecting to the mail server')
            pass
        try:
            result.login(self.config['username'], self.config['password'])
            self.log.debug('imap connection successfully established')
        except:
            self.log.error('connectMail, error while logging in')
            pass
        return result
