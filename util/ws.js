#!/usr/bin/node
/*
 * Copyright (C) 2015-2021 Amarisoft
 * WebSocket example version 2021-09-18
 */

var fs = require("fs");
var tls = require('tls');

var server = null;
var ssl    = false;
var notif  = false;
var define = {};
var timeout = 10 * 60; // 10min
var password = null;

console.log("WebSocket remote API tool version 2021-09-18, Copyright (C) 2012-2021 Amarisoft");

function Help()
{
    console.error("Send messages:");
    console.error("  >", process.argv[1], "[options]", "<server name>", "[[<msg0> | -f <file0>]", "[<msg1> | -f <file1>]", "...]");
    console.error("  Examples:");
    console.error("    >", process.argv[1], "127.0.0.1:9000", "'{\"message\": \"config_get\"}'");
    console.error("    >", process.argv[1], "127.0.0.1:9000", "-f", '"message.json"');
    console.error("    >", process.argv[1], "127.0.0.1:9000", "'{\"message\": \"log_get\"}'", 'null', "'{\"message\": \"log_get\"}'");
    console.error("Listen mode:");
    console.error("  >", process.argv[1], "[options]", "<server name>", "-l");
    console.error("Listen for an event:");
    console.error("  >", process.argv[1], "[options]", "<server name>", "-e", "\"<event name>\"", "-l");
    console.error("Wait between messages:");
    console.error("  >", process.argv[1], "[options]", "<server name>", "<msg0>", "-w <delay in seconds>", "<msg1>", "...");
    console.error("Options:");
    console.error("    --ssl: use SSL socket");
    console.error("    -t <timeout in s>: message timeout (default is 10min)");
    console.error("    -d <name> <value>: set name/value couple to replace in messages %<name>% pattern to <value>");
    console.error("    -p <password>: password used for authentication");
    process.exit(1);
};

// Server name must be provided
var cmdList = [];
for (var i = 2; i < process.argv.length; i++) {
    var arg = process.argv[i];

    switch (arg) {
    case '--ssl':
        ssl = true;
        break;
    case '-p':
        password = process.argv[++i];
        break;
    case '-l':
        cmdList.push({type: 'listen'});
        break;
    case '-w':
        cmdList.push({type: 'wait', delay: process.argv[++i] - 0});
        break;
    case '-e':
        cmdList.push({type: 'msg', msg: '{"message": "register", "register": [' + JSON.stringify(process.argv[++i]) + ']}'});
        break;
    case '-f':
        cmdList.push({type: 'msg', msg: fs.readFileSync(process.argv[++i], "utf8")});
        break;
    case '-d':
        var name = process.argv[++i];
        define[name] = process.argv[++i];
        break;
    case '-n':
        notif = true;
        break;
    case '-t':
        timeout = Math.max(1, process.argv[++i] >>> 0);
        break;
    case '-h':
    case '--help':
        Help();
        break;
    default:
        if (!server) {
            server = arg;
        } else {
            cmdList.push({type: 'msg', msg: arg});
        }
        break;
    }
}

switch (server) {
case null:
case undefined:
case '':
    Help();
    break;
case 'mme':
    server = '127.0.0.1:9000';
    break;
case 'enb':
    server = '127.0.0.1:9001';
    break;
case 'ue':
    server = '127.0.0.1:9002';
    break;
case 'ims':
    server = '127.0.0.1:9003';
    break;
case 'mbms':
    server = '127.0.0.1:9004';
    break;
case 'n3iwf':
    server = '127.0.0.1:9005';
    break;
case 'license':
    server = '127.0.0.1:9006';
    break;
case 'mon':
    server = '127.0.0.1:9007';
    break;
case 'view':
    server = '127.0.0.1:9008';
    break;
case 'scan':
    server = '127.0.0.1:9009';
    break;
case 'probe':
    server = '127.0.0.1:9010';
    break;
}

/*
 * Check WebSocket module is present
 * If not, npm is required to download it
 */
try {
    var WebSocket = require('nodejs-websocket');
} catch (e) {
    console.error("Missing nodejs WebSocket module", e);
    console.error("Please install it:");
    console.error("  npm required:");
    console.error("    > dnf install -y npm");
    console.error("  module installation:");
    console.error("    > npm install -g nodejs-websocket");
    console.error("    or");
    console.error("    > npm install nodejs-websocket");
    process.exit(1);
}

// Create WebSocket client
var listen  = false;
var msg_id  = 0;
var arg_idx = 3;

var options = {extraHeaders: {"origin": "Test"}};
var proto = 'ws';
if (ssl) {
    //process.env['NODE_TLS_REJECT_UNAUTHORIZED'] = '0';
    options.rejectUnauthorized = false;
    proto = 'wss';

    /*options.secureContext = tls.createSecureContext({
        ca: fs.readFileSync('xxx'),
        key: fs.readFileSync('xxx'),
        cert: fs.readFileSync('xxx'),
    });*/
}
var ws = WebSocket.connect(proto + '://' + server + '/', options);
var connectTimer = setTimeout(function () {
    console.error(getHeader(), "!!! Connection timeout");
    process.exit(1);
}, timeout * 1000);

// Callbacks
ws.on('connect', function () {

    console.log(getHeader(), "### Connected to", server);
});

ws.on('text', function (msg) {

    var msg0 = JSON.parse(msg);

    if (msg0) {
        switch (msg0.message) {
        case 'authenticate':
            if (msg0.ready) {
                console.log(getHeader(), '### Authenticated');
                Start();
                return;
            }

            if (!password) {
                console.error(getHeader(), 'Authentication required, use -p option');
                process.exit(1);
            }

            if (msg0.error) {
                console.error(getHeader(), '### Authentication error:', msg0.error);
                process.exit(1);
            }
            console.log(getHeader(), '### Authentication required: name=' + msg0.name + ', type=' + msg0.type + ', version=' + msg0.version);

            var hmac = require('crypto').createHmac('sha256', msg0.type + ':' + password + ':' + msg0.name);
            hmac.update(msg0.challenge);
            ws.send(JSON.stringify({message: 'authenticate', res: hmac.digest('hex')}));
            return;
        case 'ready':
            console.log(getHeader(), '### Ready: name=' + msg0.name + ', type=' + msg0.type + ', version=' + msg0.version);
            Start();
            return;
        }
    }

    var index = -1;

    for (var i = 0; i < sentList.length; i++) {
        if (sentList[i].message_id === msg0.message_id) {
            var msg1 = sentList[i];
            break;
        }
    }

    if (msg1 || listen) {
        console.log(getHeader(), "==> Message received");
        console.log(JSON.stringify(msg0, null, 4));

        if (msg1 && (!msg0.notification || notif)) {
            sentList.splice(sentList.indexOf(msg1), 1);
            clearTimeout(msg1.__timer__);
            checkNext();
        }
    }
});

ws.on('binary', function (stream) {

    stream.once('readable', function () {

        var data = stream.read(4);
        var size = data.readUInt32LE(0);
        var json = stream.read(size);
        var size = data.readUInt32LE(0);
        console.log(getHeader(), '==> Binary received', size, 'bytes');
        console.log(JSON.parse(json));

        stream.read(size);
    });
});

ws.on('close', function () {
    console.log(getHeader(), "!!! Disconnected");
    process.exit(0);
});

ws.on('error', function (err) {
    console.error(getHeader(), "!!! Error", err);
    process.exit(1);
});


var msgTimeout = function (msg)
{
    console.error(getHeader(), "!!! Message timeout", msg);
    process.exit(1);
}

var Start = function ()
{
    clearTimeout(connectTimer);
    connectTimer = 0;
    checkNext();
}

var startTime = new Date() * 1;
var getHeader = function () {
    return '[' + ((new Date() - startTime) / 1000).toFixed(3) + ']';
};

var sentList = [];
var checkNext = function()
{
    if (sentList.length || listen)
        return;

    if (!cmdList.length)
        process.exit(0);

    var msgList = [];
    var cmd = cmdList.shift();
    switch (cmd.type) {
    case 'listen':
        listen = true;
        break;

    case 'wait':
        console.log(getHeader(), '*** Wait for', cmd.delay.toFixed(1), 's');
        setTimeout(checkNext, cmd.delay * 1000);
        return false;

    case 'msg':
        var data = cmd.msg;
        for (var i in define)
            data = data.replace(new RegExp('%' + i + '%', 'g'), define[i]);

        try {
            var list = JSON.parse(data);
        } catch (e) {
            console.error(getHeader(), "JSON error on sent message:", data);
            console.error(e);
            process.exit(1);
        }
        if (!(list instanceof Array)) list = [list];

        for (var i in list) {
            var msg = list[i];
            if (msg.message_id === undefined)
                msg.message_id = "id#" + (++msg_id);
            msgList.push(msg);
            console.log(getHeader(), '<== Send message', msg.message, msg.message_id);
        }
        break;
    }

    // Send ?
    if (!msgList.length)
        return checkNext();

    if (msgList.length == 1) {
        ws.send(JSON.stringify(msgList[0]));
    } else {
        ws.send(JSON.stringify(msgList));
    }

    for (var i = 0; i < msgList.length; i++) {
        sentList.push(msgList[i]);
        msgList[i].__timer__ = setTimeout(msgTimeout.bind(this, msgList[i]), timeout * 1000);
    }
};


