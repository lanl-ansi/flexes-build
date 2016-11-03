var jobId;

$(function () {
  $.material.init();
});

$('body').on('click', '#PopEconSubmit', function () {
  var input = $('#PopEconInput').val();
  $.post('./popecon', input, function(response) {
    jobId = response.jobId;
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
