var jobId;

$(function () {
  $.ajaxSetup({contentType: 'application/json'})
  $.material.init();
});

$('body').on('click', '#PopEconSubmit', function () {
  var input = $('#PopEconInput').val();
  $.post('./popecon', input, function(response) {
    jobId = response.job_id;
    $('#PopEconQueryDiv').show(1000);
  });
});

$('body').on('click', '#PopEconQueryBtn', function () {
  var url = './popecon/jobs/' + jobId;
  $.get(url, function(response) {
    $('#PopEconQueryResult').empty();
    $('#PopEconQueryResult').text(JSON.stringify(response));
  })
});
