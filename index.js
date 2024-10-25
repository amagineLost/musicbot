const { Client, GatewayIntentBits, REST, Routes, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { Player } = require('discord-player');
const ytdl = require('ytdl-core');
require('@discord-player/downloader');
const { YoutubeiExtractor } = require('discord-player-youtubei');

// Use environment variables
const token = process.env.DISCORD_TOKEN;
const clientId = process.env.DISCORD_CLIENT_ID;
const guildId = process.env.DISCORD_GUILD_ID;

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildVoiceStates,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.GuildMembers
    ]
});

// Initialize the player
const player = new Player(client, {
    bufferingTimeout: 3000, // Increased buffer timeout
    leaveOnEnd: false,      // Prevent bot from leaving when the queue ends
    leaveOnStop: false,     // Prevent bot from leaving when stopped
    leaveOnEmpty: true,     // Leave if the voice channel is empty
    initialVolume: 50,
    crossfade: true         // Enable smooth transitions between tracks
});

// Register the YouTube Extractor
player.extractors.register(YoutubeiExtractor);

const rest = new REST({ version: '10' }).setToken(token);

// Register slash commands for a single guild (your server)
(async () => {
    try {
        console.log('Started refreshing application (/) commands.');

        await rest.put(
            Routes.applicationGuildCommands(clientId, guildId),
            {
                body: [
                    {
                        name: 'play',
                        description: 'Plays a song from YouTube or Spotify',
                        options: [{
                            name: 'query',
                            type: 3, // String type
                            description: 'The URL or name of the song to play',
                            required: true
                        }]
                    },
                    {
                        name: 'queue',
                        description: 'Displays the current music queue'
                    },
                    {
                        name: 'volume',
                        description: 'Adjust the music volume',
                        options: [{
                            name: 'level',
                            type: 4, // Integer
                            description: 'Volume level from 1 to 100',
                            required: true
                        }]
                    },
                    {
                        name: 'shuffle',
                        description: 'Shuffle the music queue'
                    },
                    {
                        name: 'seek',
                        description: 'Seek to a specific time in the current track',
                        options: [{
                            name: 'time',
                            type: 3, // String (HH:MM or MM:SS format)
                            description: 'The time to seek to in the current track',
                            required: true
                        }]
                    },
                    {
                        name: 'lyrics',
                        description: 'Fetches lyrics for the current song'
                    }
                ]
            }
        );

        console.log('Successfully reloaded application (/) commands.');
    } catch (error) {
        console.error(error);
    }
})();

client.once('ready', () => {
    console.log(`${client.user.tag} is online!`);
});

// Queue Idle timeout - auto-leave
player.on('emptyQueue', (queue) => {
    setTimeout(() => {
        if (queue.tracks.length === 0) {
            queue.metadata.channel.send('No more songs in queue, leaving the voice channel.');
            queue.destroy();
        }
    }, 300000); // 5 minutes
});

client.on('interactionCreate', async interaction => {
    if (!interaction.isCommand()) return;

    const { commandName, options } = interaction;

    // Play command
    if (commandName === 'play') {
        const query = options.getString('query');

        if (!interaction.member.voice.channel) {
            return interaction.reply('You need to be in a voice channel to play music!');
        }

        await interaction.deferReply();

        const queue = await player.nodes.create(interaction.guild, {
            metadata: { channel: interaction.channel },
            bufferingTimeout: 3000,
            leaveOnEnd: false,
            leaveOnStop: false,
            leaveOnEmpty: true,
            initialVolume: 50,
            crossfade: true
        });

        try {
            if (!queue.connection) await queue.connect(interaction.member.voice.channel);

            const trackInfo = await ytdl.getInfo(query);
            const track = {
                title: trackInfo.videoDetails.title,
                url: trackInfo.videoDetails.video_url,
                author: trackInfo.videoDetails.author.name,
                duration: trackInfo.videoDetails.lengthSeconds,
                thumbnail: trackInfo.videoDetails.thumbnails[0].url
            };

            queue.play(track);

            const embed = new EmbedBuilder()
                .setTitle('Now Playing')
                .setDescription(`🎵 **${track.title}**\n🕒 ${track.duration} seconds\n👤 ${track.author}`)
                .setThumbnail(track.thumbnail)
                .setURL(track.url);

            await interaction.followUp({ embeds: [embed] });
        } catch (error) {
            console.error(error);
            interaction.followUp('There was an error processing your request.');
        }
    }

    // Queue command
    if (commandName === 'queue') {
        const queue = player.nodes.get(interaction.guild.id);
        if (!queue || !queue.tracks.length) {
            return interaction.reply('The queue is empty.');
        }
        const tracks = queue.tracks.slice(0, 10).map((track, i) => `${i + 1}. ${track.title} - ${track.author}`);
        const embed = new EmbedBuilder()
            .setTitle('Current Queue')
            .setDescription(tracks.join('\n'))
            .setFooter({ text: `Total: ${queue.tracks.length} tracks` });
        interaction.reply({ embeds: [embed] });
    }

    // Volume command
    if (commandName === 'volume') {
        const level = options.getInteger('level');
        if (level < 1 || level > 100) return interaction.reply('Volume must be between 1 and 100.');
        const queue = player.nodes.get(interaction.guild.id);
        if (!queue || !queue.node.isPlaying()) return interaction.reply('No music is playing.');
        queue.node.setVolume(level);
        interaction.reply(`Volume set to ${level}%`);
    }

    // Shuffle command
    if (commandName === 'shuffle') {
        const queue = player.nodes.get(interaction.guild.id);
        if (!queue || !queue.tracks.length) return interaction.reply('The queue is empty.');
        queue.shuffle();
        interaction.reply('Shuffled the queue!');
    }

    // Seek command
    if (commandName === 'seek') {
        const time = options.getString('time');
        const queue = player.nodes.get(interaction.guild.id);
        if (!queue || !queue.node.isPlaying()) return interaction.reply('No music is playing.');

        const [minutes, seconds] = time.split(':').map(Number);
        const seekTime = (minutes * 60) + (seconds || 0);
        queue.node.seek(seekTime * 1000); // Convert to milliseconds
        interaction.reply(`Seeked to ${time}`);
    }

    // Lyrics command
    if (commandName === 'lyrics') {
        const queue = player.nodes.get(interaction.guild.id);
        if (!queue || !queue.node.isPlaying()) return interaction.reply('No music is playing.');

        const track = queue.current;
        try {
            const lyrics = await fetchLyrics(track.title); // Replace with actual lyrics fetching logic
            if (!lyrics) return interaction.reply('No lyrics found for this song.');

            const embed = new EmbedBuilder()
                .setTitle(`Lyrics for ${track.title}`)
                .setDescription(lyrics.slice(0, 4096)); // Discord embeds limit to 4096 characters
            interaction.reply({ embeds: [embed] });
        } catch (error) {
            console.error(error);
            interaction.reply('Failed to fetch lyrics.');
        }
    }
});

// Error handling for player
player.on('error', (queue, error) => {
    console.error(`Error in queue: ${error.message}`);
    if (queue.metadata.channel) {
        queue.metadata.channel.send('An error occurred while playing the music.');
    }
});

// Mock function to simulate fetching lyrics (use an actual API or module)
async function fetchLyrics(trackTitle) {
    return `Lyrics for ${trackTitle}`; // Replace with actual API integration for lyrics
}

// Login to Discord
client.login(token);
