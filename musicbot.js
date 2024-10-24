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
        GatewayIntentBits.GuildMembers // Added GuildMembers intent to check roles
    ]
});

// Initialize the player
const player = new Player(client);

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
                    // Add other command registrations if needed...
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

client.on('interactionCreate', async interaction => {
    if (interaction.isCommand()) {
        const { commandName, options } = interaction;

        // Play command
        if (commandName === 'play') {
            const query = options.getString('query');

            if (!interaction.member.voice.channel) {
                return interaction.reply('You need to be in a voice channel to play music!');
            }

            const queue = await player.nodes.create(interaction.guild, {
                metadata: {
                    channel: interaction.channel
                }
            });

            try {
                if (!queue.connection) await queue.connect(interaction.member.voice.channel, { deaf: false });
            } catch {
                queue.destroy();
                return interaction.reply('Could not join your voice channel!');
            }

            try {
                const track = await player.search(query, {
                    requestedBy: interaction.user,
                    searchEngine: 'youtube'
                }).then(x => x.tracks[0]);

                if (!track) return interaction.reply(`Track ${query} not found!`);

                // Play the track
                queue.play(track);
                queue.node.setVolume(50); // Default volume

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

                // Send the embed with the action row (buttons)
                await interaction.reply({ embeds: [embed], components: [row] });
            } catch (error) {
                console.error(error);
                interaction.reply('There was an error processing your request.');
            }
        }
    }

    // Button handling
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
                await interaction.update({ content: 'Unknown command!', ephemeral: true });
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

// Login to Discord
client.login(token);
