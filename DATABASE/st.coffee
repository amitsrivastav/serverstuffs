elasticsearch_hostname = process.env.ELASTICSEARCH_HOSTNAME || 'localhost:7200'elasticsearch_url = "http://" + elasticsearch_hostname + "/"print_result = (err,res,body,msg) ->  if(err)    msg.send err    msg.send res    msg.send body  else    data = JSON.parse body    logs = data.hits.hits.sort (a,b) -> if a._source.date > b._source.date then 1 else -1    msg.send "#{log._source.message}" for log in logssearch_syslog_stacktrace = (msg, data) ->  data = JSON.stringify(data)  msg.http(elasticsearch_url + "docker-syslog-*/_search" )  .header('Content-Length', data.length)  .post(data) (err, res, body) ->    print_result(err, res, body, msg)search_gelf_stacktrace = (msg, data) ->  data = JSON.stringify(data)  msg.http(elasticsearch_url + "docker-gelf-*/_search" )  .header('Content-Length', data.length)  .post(data) (err, res, body) ->    print_result(err, res, body, msg)module.exports = (robot) ->  robot.respond /get the stacktrace from Docker 1.7 logs (.+)/i, (msg) ->    query_data = msg.match[1].split " "    data = { query: { bool : { must : [ { term : {"CREATED_AT.keyword" : query_data[0].trim()+ " " + query_data[1].trim() } }, { term : {"LOG_LEVEL.keyword" : query_data[2].trim() } } ] }}}    search_syslog_stacktrace(msg,data)  robot.respond /get the stacktrace from Docker 1.13 logs (.+)/i, (msg) ->     query_gelf_data = msg.match[1].split " "     data = { query: { bool : { must : [ { term : {"CREATED_AT.keyword" : query_gelf_data[0].trim()+ " " + query_gelf_data[1].trim() } }, { term : {"LOG_LEVEL.keyword" : query_gelf_data[2].trim() } } ] }}}     search_gelf_stacktrace(msg,data)