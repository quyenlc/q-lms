$(document).ready(function() {
   $(':input[name$=software]').on('change', function() {
       var prefix = $(this).getFormPrefix();
       $(':input[name=' + prefix + 'platform]').val(null).trigger('change');
   });

   $(':input[name$=platform]').on('change', function() {
       var prefix = $(this).getFormPrefix();
       $(':input[name=' + prefix + 'license]').val(null).trigger('change');
       $(':input[name=' + prefix + 'license_key]').val(null).trigger('change');
   });

   $(':input[name$=license]').on('change', function() {
       var prefix = $(this).getFormPrefix();
       $(':input[name=' + prefix + 'license_key]').val(null).trigger('change');
   });
});     