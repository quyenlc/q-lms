$(document).ready(function() {
   $(':input[name$=platform]').on('change', function() {
       var prefix = $(this).getFormPrefix();
       $(':input[name=' + prefix + 'softwares]').val(null).trigger('change');
   });
});