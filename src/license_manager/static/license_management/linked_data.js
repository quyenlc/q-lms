$(document).ready(function() {
   $(':input[name$=software]').on('change', function() {
       var prefix = $(this).getFormPrefix();
       $(':input[name=' + prefix + 'license]').val(null).trigger('change');
   });
});     