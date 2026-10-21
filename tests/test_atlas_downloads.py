"""Native document bytes, missing sources and fail-closed publication checks."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from design_atlas import downloads, refresh


class DocumentDownloads(unittest.TestCase):
    def setUp(self):
        qa=refresh.build.ROOT/'design_atlas/qa'
        qa.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=qa)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.payload=b'\x00native\xff\r\nbytes'*7
        (self.root/'journal.bpad').write_bytes(self.payload)
        self.data={'nodes':[{'id':'journal','path':'journal.bpad'},
                            {'id':'module','path':'journal.bpad','module':'CapDesignPier'},
                            {'id':'absent','path':'missing.xml'}, {'id':'unlinked'}],
                   'documents':{'journal.bpad':{'exists':True,'sha256':hashlib.sha256(self.payload).hexdigest()},
                                'missing.xml':{'exists':False,'sha256':None}}}

    def attach(self):
        with patch.object(downloads,'PART_BYTES',17):downloads.attach_downloads(self.data,self.root)

    def test_exact_binary_download_and_shared_journal(self):
        self.attach()
        output=self.root/'out'
        downloads.write_downloads(self.data,output,self.root)
        document=self.data['documents']['journal.bpad']['download']
        self.assertEqual(document['filename'],'journal.bpad')
        self.assertEqual(document['bytes'],len(self.payload))
        self.assertGreater(len(document['parts']),1)
        self.assertEqual(b''.join((output/p['href']).read_bytes() for p in document['parts']),self.payload)
        self.assertEqual(self.data['nodes'][1]['download'],{'status':'available','path':'journal.bpad','scope':'journal'})
        self.assertEqual(self.data['nodes'][2]['download']['status'],'missing')
        self.assertEqual(self.data['nodes'][3]['download']['status'],'missing')

    def test_changed_source_blocks_packaging(self):
        self.attach()
        (self.root/'journal.bpad').write_bytes(b'edited')
        with self.assertRaisesRegex(RuntimeError,'changed'):downloads.write_downloads(self.data,self.root/'out',self.root)

    def test_exact_committed_documents_use_verified_external_links(self):
        sha=self.data['documents']['journal.bpad']['sha256']
        record={'repository':'https://github.com/owner/repo','commit':'a'*40,
                'href':'https://raw.githubusercontent.com/owner/repo/'+'a'*40+'/journal.bpad',
                'bytes':len(self.payload),'sha256':sha}
        with patch.object(downloads,'committed_document',return_value=record):self.attach()
        doc=self.data['documents']['journal.bpad']['download']
        self.assertEqual(doc['parts'][0]['href'],record['href'])
        downloads.write_downloads(self.data,self.root/'out',self.root)
        self.assertFalse((self.root/'out/downloads').exists())
        (self.root/'journal.bpad').write_bytes(b'edited')
        with self.assertRaisesRegex(RuntimeError,'changed'):downloads.write_downloads(self.data,self.root/'out',self.root)

    def test_different_committed_bytes_keep_exact_local_document(self):
        with patch.object(downloads,'committed_document',return_value={'sha256':'older'}):self.attach()
        doc=self.data['documents']['journal.bpad']['download']
        self.assertNotIn('repository',doc)
        self.assertTrue(doc['parts'][0]['href'].startswith('downloads/'))

    def test_private_or_unpublished_external_documents_block_staging(self):
        data={'documents':{'file':{'download':{'repository':'https://github.com/owner/repo','commit':'a'*40}}}}
        response=MagicMock()
        response.__enter__.return_value.read.return_value=b'{"private":true,"default_branch":"main"}'
        with patch.object(downloads,'urlopen',return_value=response):
            with self.assertRaisesRegex(RuntimeError,'not public'):downloads.verify_remote_downloads(data,self.root)
        response.__enter__.return_value.read.return_value=b'{"private":false,"default_branch":"main"}'
        with patch.object(downloads,'urlopen',return_value=response), \
             patch.object(downloads.subprocess,'check_output',return_value='b'*40+'\trefs/heads/main\n'), \
             patch.object(downloads.subprocess,'run',return_value=MagicMock(returncode=1)):
            with self.assertRaisesRegex(RuntimeError,'not on the public'):downloads.verify_remote_downloads(data,self.root)

    def test_paths_cannot_leave_repository(self):
        for path in ('../outside','C:/outside'):
            with self.assertRaises(ValueError):downloads.source_path(self.root,path)

    def test_obsolete_downloads_are_removed_and_artifacts_detect_tampering(self):
        self.attach();output=self.root/'out'
        downloads.write_downloads(self.data,output,self.root)
        for name in refresh.ASSETS:(output/name).write_text('test',encoding='utf8')
        before=refresh.artifact_hashes(output)
        self.assertTrue(any(k.startswith('downloads/') for k in before))
        part=self.data['documents']['journal.bpad']['download']['parts'][0]['href']
        (output/part).write_bytes(b'tampered')
        self.assertNotEqual(before,refresh.artifact_hashes(output))
        (output/'downloads/obsolete.bin').write_bytes(b'old source')
        downloads.write_downloads(self.data,output,self.root)
        self.assertEqual(before,refresh.artifact_hashes(output))

    def test_empty_document_remains_downloadable(self):
        (self.root/'empty.json').write_bytes(b'')
        doc=downloads.describe(self.root,'empty.json',hashlib.sha256(b'').hexdigest())
        self.assertEqual(doc['bytes'],0)
        self.assertEqual(len(doc['parts']),1)


if __name__=='__main__':unittest.main()
