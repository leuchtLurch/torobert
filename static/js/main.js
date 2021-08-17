$(function(){
    $('div.card').click(function(){
        data = {'textGeneratorName': $(this).attr('data-textGeneratorName')};
        console.log(data);
        $.ajax({
            url: '/onDemandAction',
            data: data,
            type: 'POST',
            success: function(response){
                console.log(response);
            },
            error: function(error){
                console.log(error);
            }
        });
    });
});

$(function(){
    $('#cbRemoteSSH').click(function(){
        data = {'RemoteSSH': $(this).prop('checked')};
        console.log(data);
        $.ajax({
            url: '/onToggleRemoteSSH',
            data: data,
            type: 'POST',
            success: function(response){
                console.log(response);
            },
            error: function(error){
                console.log(error);
            }
        });
    });
});

$(function(){
    $('#cbTalkingInitiative').click(function(){
        data = {'talkingInitiative': $(this).prop('checked')};
        console.log(data);
        $.ajax({
            url: '/onToggleInitiative',
            data: data,
            type: 'POST',
            success: function(response){
                console.log(response);
            },
            error: function(error){
                console.log(error);
            }
        });
    });
});

$(function(){
    $('#slVolume').change(function(){
        data = {'volume': $(this).val()};
        console.log(data);
        $.ajax({
            url: '/onSetVolume',
            data: data,
            type: 'POST',
            success: function(response){
                console.log(response);
            },
            error: function(error){
                console.log(error);
            }
        });
    });
});
