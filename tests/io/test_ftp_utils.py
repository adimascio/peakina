import ftplib
import os
import socket

from pytest import fixture, raises

from peakina.io.ftp_utils import _open, dir_mtimes, ftp_listdir, ftp_mtime, ftp_open


@fixture
def ftp_client(mocker):
    connection_mock = mocker.patch('peakina.io.ftp_utils.connection')
    conn_ftp = mocker.MagicMock()
    conn_ftp.client = mocker.MagicMock()
    conn_ftp.path = 'ftpurl'
    connection_mock.return_value.__enter__.return_value = conn_ftp
    return conn_ftp.client


def test_ftps_connect():
    ftp_open('ftps://demo:password@test.rebex.net/readme.txt')


def test_open(ftp_client, mocker):
    ret = ftp_open(url='foo')
    assert ret.name.endswith('.ftptmp')  # check the suffix is the expected one
    assert os.path.exists(ret.name)
    ftp_client.retrbinary.assert_called_once()
    ret.close()
    assert not os.path.exists(ret.name)  # tmp file is deleted on .close()
    ftp_listdir(url='foo')
    ftp_client.nlst.assert_called_once()

    ftp_client.nlst.side_effect = socket.timeout
    with raises(socket.timeout):
        ftp_listdir(url='foo')

    mocker.patch('peakina.io.ftp_utils.retry_pasv').side_effect = AttributeError
    ret = ftp_open(url="foo")
    assert ret.name.endswith('.ftptmp')  # check the suffix is the expected one
    assert os.path.exists(ret.name)
    ftp_client.getfo.assert_called_once()
    ret.close()
    assert not os.path.exists(ret.name)  # tmp file is deleted on .close()
    ftp_listdir(url='foo')
    ftp_client.listdir.assert_called_once()


def test_ftp_listdir(mocker):
    """nlst now returns the parent dir. We should retrieve only the filenames"""
    client_mock = mocker.patch('peakina.io.ftp_utils.connection')
    client_mock.return_value.__enter__.return_value.client = ftplib.FTP_TLS()
    mocker.patch('ftplib.FTP.nlst').return_value = ['parent_dir/file1.csv', 'parent_dir/file2.csv']
    assert ftp_listdir('ftps://someuri') == ['file1.csv', 'file2.csv']


def test_open_ko(mocker, ftp_client):
    mocker.patch('peakina.io.ftp_utils.retry_pasv').side_effect = ftplib.error_perm
    with raises(Exception) as e:
        _open(ftp_client, 'ftpurl')
    assert str(e.value) == 'Cannot open file "ftpurl". Please make sure the file exists'


def test_retry_open(mocker, ftp_client):
    mocker.patch('peakina.io.ftp_utils._open').side_effect = [
        ftplib.error_temp('421 Could not create socket'),
        AttributeError("'NoneType' object has no attribute 'sendall'"),
        OSError('Random OSError'),
        'ok',
    ]
    mock_sleep = mocker.patch('peakina.io.ftp_utils.sleep')

    ret = ftp_open(url="foo")
    calls = [mocker.call(2), mocker.call(8), mocker.call(18)]
    mock_sleep.assert_has_calls(calls)
    assert ret == 'ok'


def test_get_mtime(ftp_client):
    ftp_client.sendcmd.return_value = '213 20180101203000'
    assert ftp_mtime(url='foo') == 1_514_838_600

    ftp_client.sendcmd.side_effect = AttributeError
    ftp_client.stat.return_value.st_mtime = 1_514_835_000
    assert ftp_mtime(url='foo') == 1_514_835_000

    ftp_client.sendcmd.side_effect = ftplib.error_perm('zbruh')
    with raises(ftplib.error_perm) as exc_info:
        ftp_mtime(url='foo')
    assert (
        str(exc_info.value) == 'Cannot open file "ftpurl". Please make sure the file exists: zbruh'
    )


def test_dir_mtimes(mocker, ftp_client):
    mocker.patch('peakina.io.ftp_utils._get_all_files').return_value = [
        'file1.csv',
        'file2.csv',
        'file3.csv',
    ]
    mocker.patch('peakina.io.ftp_utils._get_mtime').side_effect = [
        'mtime1',
        'mtime2',
        ftplib.error_perm,
    ]
    assert dir_mtimes('my_url') == {'file1.csv': 'mtime1', 'file2.csv': 'mtime2', 'file3.csv': None}


def test_ftp_client(mocker):
    mock_ftp_client = mocker.patch('ftplib.FTP').return_value

    url = 'ftp://sacha@ondine.com:123/picha/chu.csv'
    ftp_open(url)

    mock_ftp_client.connect.assert_called_once_with(host='ondine.com', port=123, timeout=3)
    mock_ftp_client.login.assert_called_once_with(passwd=None, user='sacha')
    mock_ftp_client.quit.assert_called_once()


def test_ftps_client(mocker):
    mock_ftps_client = mocker.patch('peakina.io.ftp_utils.FTPS').return_value
    url = 'ftps://sacha@ondine.com:123/picha/chu.csv'
    ftp_open(url)

    mock_ftps_client.connect.assert_called_once_with(host='ondine.com', port=123, timeout=3)
    mock_ftps_client.login.assert_called_once_with(passwd=None, user='sacha')
    mock_ftps_client.quit.assert_called_once()


def test_sftp_client(mocker):
    mock_ssh_client = mocker.patch('paramiko.SSHClient').return_value

    url = 'sftp://id#de@me*de:randompass@atat.com:666/pika/chu.csv'
    ftp_open(url)

    mock_ssh_client.connect.assert_called_once_with(
        timeout=3, hostname='atat.com', port=666, username='id#de@me*de', password='randompass'
    )
    mock_ssh_client.open_sftp.assert_called_once()
    mock_ssh_client.close.assert_called_once()

    cl_ftp = mock_ssh_client.open_sftp.return_value
    cl_ftp.sendcmd.side_effect = AttributeError
    ftp_mtime(url)
    cl_ftp.stat.assert_called_once_with('/pika/chu.csv')
