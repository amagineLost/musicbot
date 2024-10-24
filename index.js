const { Client, GatewayIntentBits, REST, Routes, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { Player } = require('discord-player');
const { token, clientId, guildId } = require('./config.json');
require('@discord-player/downloader');
const { YoutubeiExtractor } = require('discord-player-youtubei');

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
    bufferingTimeout: 3000, // Increased buffer timeout to 3 seconds
    leaveOnEnd: false,      // Prevent bot from leaving when the queue ends
    leaveOnStop: false,     // Prevent bot from leaving when stopped
    leaveOnEmpty: true,     // Leave if the voice channel is empty
    initialVolume: 50,
    crossfade: true         // Enable smooth transitions between tracks
});

// Register the YouTube Extractor
player.extractors.register(YoutubeiExtractor);

const rest = new REST({ version: '10' }).setToken(token);

// Cooldown map for command usage
let cooldowns = new Map();

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

    const now = Date.now();
    const cooldownAmount = 5000; // 5-second cooldown

    // Check if the user is in cooldown
    if (cooldowns.has(interaction.user.id)) {
        const expirationTime = cooldowns.get(interaction.user.id) + cooldownAmount;

        if (now < expirationTime) {
            const timeLeft = (expirationTime - now) / 1000;
            return interaction.reply(`Please wait ${timeLeft.toFixed(1)} more seconds before using this command.`);
        }
    }

    cooldowns.set(interaction.user.id, now);
    setTimeout(() => cooldowns.delete(interaction.user.id), cooldownAmount);

    const { commandName, options } = interaction;

    // Play command
    if (commandName === 'play') {
        const query = options.getString('query');

        if (!interaction.member.voice.channel) {
            return interaction.reply('You need to be in a voice channel to play music!');
        }

        // Defer reply to prevent timeout errors
        await interaction.deferReply();

        const queue = await player.nodes.create(interaction.guild, {
            metadata: {
                channel: interaction.channel
            },
            bufferingTimeout: 3000, // Increase buffer timeout to 3 seconds
            leaveOnEnd: false,      // Prevent bot from leaving when queue is empty
            leaveOnStop: false,     // Prevent bot from leaving on stop command
            leaveOnEmpty: true,     // Leaves if the voice channel is empty
            initialVolume: 50,
            crossfade: true         // Enable crossfade between songs
        });

        try {
            if (!queue.connection) await queue.connect(interaction.member.voice.channel, { deaf: false });
        } catch {
            queue.destroy();
            return interaction.followUp('Could not join your voice channel!');
        }

        try {
            const track = await player.search(query, {
                requestedBy: interaction.user,
                searchEngine: 'youtube'
            }).then(x => x.tracks[0]);

            if (!track) return interaction.followUp(`Track ${query} not found!`);

            queue.play(track);

            // Now Playing Embed
            const embed = new EmbedBuilder()
                .setTitle('Now Playing')
                .setDescription(`🎵 **${track.title}**\n🕒 ${track.duration}\n👤 ${track.author}`)
                .setThumbnail(track.thumbnail)
                .setURL(track.url);

            // Button Row
            const row = new ActionRowBuilder()
                .addComponents(
                    new ButtonBuilder()
                        .setCustomId('pause')
                        .setLabel('Pause')
                        .setStyle(ButtonStyle.Primary),
                    new ButtonBuilder()
                        .setCustomId('stop')
                        .setLabel('Stop')
                        .setStyle(ButtonStyle.Danger),
                    new ButtonBuilder()
                        .setCustomId('skip')
                        .setLabel('Skip')
                        .setStyle(ButtonStyle.Success),
                    new ButtonBuilder()
                        .setCustomId('loop')
                        .setLabel('Loop')
                        .setStyle(ButtonStyle.Secondary)
                );

            await interaction.followUp({ embeds: [embed], components: [row] });
        } catch (error) {
            console.error(error);
            interaction.followUp('There was an error processing your request.');
        }
    }

    // Queue command
    if (commandName === 'queue') {
        await interaction.deferReply();

        const queue = player.nodes.get(interaction.guild.id);
        if (!queue || !queue.tracks.length) {
            return interaction.followUp('The queue is empty.');
        }
        const tracks = queue.tracks.slice(0, 10).map((track, i) => `${i + 1}. ${track.title} - ${track.author}`);
        const embed = new EmbedBuilder()
            .setTitle('Current Queue')
            .setDescription(tracks.join('\n'))
            .setFooter({ text: `Total: ${queue.tracks.length} tracks` });
        interaction.followUp({ embeds: [embed] });
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
        await interaction.deferReply();

        const queue = player.nodes.get(interaction.guild.id);
        if (!queue || !queue.node.isPlaying()) return interaction.followUp('No music is playing.');

        const track = queue.current;
        try {
            const lyrics = await fetchLyrics(track.title);
            if (!lyrics) return interaction.followUp('No lyrics found for this song.');

            const embed = new EmbedBuilder()
                .setTitle(`Lyrics for ${track.title}`)
                .setDescription(lyrics.slice(0, 4096)); // Discord embeds limit to 4096 characters
            interaction.followUp({ embeds: [embed] });
        } catch (error) {
            console.error(error);
            interaction.followUp('Failed to fetch lyrics.');
        }
    }
});

// Button handling
client.on('interactionCreate', async interaction => {
    if (interaction.isButton()) {
        const queue = player.nodes.get(interaction.guild.id);

        if (!queue) {
            return interaction.update({ content: 'There is no active queue.', ephemeral: true });
        }

        switch (interaction.customId) {
            case 'pause':
                if (queue.node.isPlaying()) {
                    queue.node.pause();
                    await interaction.update({ content: 'Paused the music.' });
                } else {
                    queue.node.resume();
                    await interaction.update({ content: 'Resumed the music.' });
                }
                break;
            case 'stop':
                queue.destroy();
                await interaction.update({ content: 'Stopped the music and cleared the queue.' });
                break;
            case 'skip':
                queue.skip();
                await interaction.update({ content: 'Skipped the current track.' });
                break;
            case 'loop':
                const loopMode = queue.repeatMode === 1 ? 0 : 1;
                queue.setRepeatMode(loopMode);
                await interaction.update({ content: `Loop is now ${loopMode === 1 ? 'enabled' : 'disabled'}.` });
                break;
            default:
                await interaction.update({ content: 'Unknown button interaction.', ephemeral: true });
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
    // Implement the actual lyrics fetching logic here, this is just a placeholder
    return `Lyrics for ${trackTitle}`;
}

// Login to Discord
client.login(token);
