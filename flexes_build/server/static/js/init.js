var jobId;

$(function () {
  $.ajaxSetup({contentType: 'application/json'})
  $.material.init();
});

$('body').on('click', '.job-submit', function () {
  var service = $(this).val();
  var input = $('#ServiceInput').val();
  $.post('./' + service, input, function(response) {
    jobId = response.job_id;
    $('.query-result').empty();
    $('#QueryDiv').show(1000);
  });
});

$('body').on('click', '.job-check', function () {
  var service = $(this).val();
  var url = './' + service + '/jobs/' + jobId;
  $.get(url, function(response) {
    $('.query-result').empty();
    $('.query-result').text(JSON.stringify(response));
  })
});
