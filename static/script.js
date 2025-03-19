document.addEventListener("DOMContentLoaded", function () {
	const form = document.getElementById("generatorForm");
	const generateBtn = document.getElementById("generateBtn");
	const statusContainer = document.getElementById("statusContainer");
	const statusText = document.getElementById("statusText");
	const resultsContainer = document.getElementById("resultsContainer");
	const errorContainer = document.getElementById("errorContainer");
	const errorText = document.getElementById("errorText");
	const configBtn = document.getElementById("configBtn");
	const configPanel = document.getElementById("configPanel");
	const geminiApiKeyInput = document.getElementById("geminiApiKey");
	const falApiKeyInput = document.getElementById("falApiKey");
	const elevenLabsApiKeyInput = document.getElementById("elevenLabsApiKey");
	const saveGeminiKeyBtn = document.getElementById("saveGeminiKey");
	const saveFalKeyBtn = document.getElementById("saveFalKey");
	const saveElevenLabsKeyBtn = document.getElementById("saveElevenLabsKey");

	// Function to handle voice selection toggle
	function handleVoiceSelection() {
		const voiceSelection = document.getElementById("voiceSelection");
		if (!voiceSelection) return; // Guard clause to prevent errors

		const selectionType = voiceSelection.value;
		const presetContainer = document.getElementById("presetVoiceContainer");

		// Add the custom voice container if it doesn't exist
		let customContainer = document.getElementById("customVoiceContainer");
		if (!customContainer) {
			customContainer = document.createElement("div");
			customContainer.id = "customVoiceContainer";
			customContainer.className = "control-item hidden";
			customContainer.innerHTML = `
				<label for="customVoiceId">Custom Voice ID</label>
				<input type="text" id="customVoiceId" placeholder="Enter custom voice ID">
			`;

			// Insert after presetContainer
			if (presetContainer && presetContainer.parentNode) {
				presetContainer.parentNode.appendChild(customContainer);
			}
		}

		if (selectionType === "preset") {
			if (presetContainer) presetContainer.classList.remove("hidden");
			customContainer.classList.add("hidden");
			// Enable the preset voice ID for form submission
			const voiceId = document.getElementById("voiceId");
			const customVoiceId = document.getElementById("customVoiceId");
			if (voiceId && customVoiceId) {
				voiceId.setAttribute("name", "voice_id");
				customVoiceId.removeAttribute("name");
			}
		} else {
			if (presetContainer) presetContainer.classList.add("hidden");
			customContainer.classList.remove("hidden");
			// Enable the custom voice ID for form submission
			const voiceId = document.getElementById("voiceId");
			const customVoiceId = document.getElementById("customVoiceId");
			if (voiceId && customVoiceId) {
				customVoiceId.setAttribute("name", "voice_id");
				voiceId.removeAttribute("name");
			}
		}
	}

	// Add event listener for voice selection change
	const voiceSelection = document.getElementById("voiceSelection");
	if (voiceSelection) {
		voiceSelection.addEventListener("change", function () {
			handleVoiceSelection();
		});

		// Initialize the voice selection on page load
		handleVoiceSelection();
	}

	let statusCheckInterval;
	let currentGenerationId = null;

	form.addEventListener("submit", async function (e) {
		e.preventDefault();

		// Disable form and show status
		generateBtn.disabled = true;
		statusContainer.classList.remove("hidden");
		errorContainer.classList.add("hidden");

		statusText.textContent = "Generating...";

		// Get form data
		const formData = new FormData(form);

		// Add the initial image ID if it exists
		const initialImageId = document.getElementById("initialImageId").value;
		if (initialImageId) {
			formData.append("initial_image_id", initialImageId);
		}

		// Add the video model selection if video generation is enabled
		if (document.getElementById("generateVideos").checked) {
			const videoModel = document.getElementById("videoModel").value;
			formData.append("video_model", videoModel);
		} else {
			// Add default model even if videos aren't being generated
			formData.append("video_model", "fal-ai/veo2/image-to-video");
		}

		// Add background music
		const backgroundMusicUrl =
			document.getElementById("backgroundMusicUrl").value;
		if (backgroundMusicUrl) {
			formData.append("background_music", backgroundMusicUrl);
		}

		formData.append(
			"background_music_volume",
			document.getElementById("backgroundMusicVolume").value / 100
		);

		try {
			// Start generation
			const response = await fetch("/generate", {
				method: "POST",
				body: formData,
			});

			if (!response.ok) {
				throw new Error(`Server error: ${response.status}`);
			}

			const data = await response.json();
			currentGenerationId = data.id;

			// Start checking status
			statusText.textContent = "Generating...";

			// Check status every 2 seconds
			statusCheckInterval = setInterval(checkStatus, 2000);
		} catch (error) {
			showError(error.message);
			generateBtn.disabled = false;
		}
	});

	async function checkStatus() {
		try {
			const response = await fetch("/status");
			const results = await response.json();

			// Find our current generation
			const currentResult = results.find((r) => r.id === currentGenerationId);

			if (!currentResult) {
				clearInterval(statusCheckInterval);
				showError("Generation not found");
				generateBtn.disabled = false;
				return;
			}

			switch (currentResult.status) {
				case "running":
					statusText.textContent = "Generating...";
					break;

				case "completed":
					clearInterval(statusCheckInterval);
					statusText.textContent = "Generation completed!";

					// Show results
					updateResults(results);

					// Re-enable form
					generateBtn.disabled = false;

					// Hide status after a delay
					setTimeout(() => {
						statusContainer.classList.add("hidden");
					}, 2000);
					break;

				case "error":
					clearInterval(statusCheckInterval);
					showError(currentResult.error);
					generateBtn.disabled = false;
					break;
			}
		} catch (error) {
			clearInterval(statusCheckInterval);
			showError("Error checking status: " + error.message);
			generateBtn.disabled = false;
		}
	}

	function updateResults(results) {
		console.log("Updating results:", results);

		// Clear existing results
		resultsContainer.innerHTML = "";

		// Add each result
		results.forEach((result) => {
			if (result.status === "completed") {
				console.log(`Processing completed result #${result.id}`, result);

				// Check if we need to verify final video existence
				if (!result.final_video_path || result.final_video_path === "") {
					// Try to check if final video exists by constructing the expected path
					const outputDir = result.output_dir;
					if (outputDir) {
						const potentialFinalVideoPath = `${outputDir}/final_video.mp4`;
						console.log(
							`Checking for potential final video at: ${potentialFinalVideoPath}`
						);

						// Use fetch with HEAD request to check if file exists
						fetch(`/${potentialFinalVideoPath}?t=${new Date().getTime()}`, {
							method: "HEAD",
						})
							.then((response) => {
								if (response.ok) {
									console.log(
										`Final video exists at ${potentialFinalVideoPath}`
									);
									// Update the result object
									result.final_video_path = potentialFinalVideoPath;
									// Re-render this specific result
									updateSingleResult(result);
								} else {
									console.log(
										`No final video found at ${potentialFinalVideoPath} (status: ${response.status})`
									);
								}
							})
							.catch((error) => {
								console.error(`Error checking for final video: ${error}`);
							});
					}
				}

				const resultElement = document.createElement("div");
				resultElement.className = "result-item";
				resultElement.dataset.id = result.id;

				// Add title
				const title = document.createElement("div");
				title.className = "result-title";
				title.textContent = `Generation #${result.id}`;
				resultElement.appendChild(title);

				// Add slideshow video if available
				if (result.video_path) {
					console.log(
						`Adding slideshow video for #${result.id}: ${result.video_path}`
					);

					const videoContainer = document.createElement("div");
					videoContainer.className = "video-container";

					const videoHeader = document.createElement("div");
					videoHeader.className = "video-header";

					const videoTitle = document.createElement("h3");
					videoTitle.textContent = "Slideshow Video";

					const downloadBtn = document.createElement("button");
					downloadBtn.className = "download-btn";
					downloadBtn.innerHTML =
						'<span class="download-icon">⬇️</span> Download';
					downloadBtn.addEventListener("click", function () {
						const videoElement = videoContainer.querySelector("video");
						if (videoElement && videoElement.src) {
							downloadVideo(videoElement.src, "hongos_slideshow.mp4");
						}
					});

					videoHeader.appendChild(videoTitle);
					videoHeader.appendChild(downloadBtn);
					videoContainer.appendChild(videoHeader);

					const video = document.createElement("video");
					video.controls = true;
					// Add timestamp to prevent caching
					video.src = "/" + result.video_path + "?t=" + new Date().getTime();
					videoContainer.appendChild(video);

					// Add process button if no final video yet
					if (!result.final_video_path) {
						console.log(
							`No final video for #${result.id}, adding process button`
						);

						const processBtn = document.createElement("button");
						processBtn.className = "process-btn";
						processBtn.textContent = "Generate Full Video";
						processBtn.onclick = () => processFolder(result.id);
						videoContainer.appendChild(processBtn);

						// Add processing status container (initially hidden)
						const processingStatus = document.createElement("div");
						processingStatus.className = "processing-status hidden";
						processingStatus.id = `processing-status-${result.id}`;
						videoContainer.appendChild(processingStatus);
					} else {
						console.log(
							`Final video already exists for #${result.id}, not adding process button`
						);
					}

					resultElement.appendChild(videoContainer);
				}

				// Add final video if available
				if (result.final_video_path) {
					console.log(
						`Adding final video for #${result.id}: ${result.final_video_path}`
					);

					const finalVideoContainer = document.createElement("div");
					finalVideoContainer.className = "video-container";
					finalVideoContainer.id = `final-video-container-${result.id}`;

					const finalVideoHeader = document.createElement("div");
					finalVideoHeader.className = "video-header";

					const finalVideoTitle = document.createElement("h3");
					finalVideoTitle.textContent = "Final Video";
					finalVideoHeader.appendChild(finalVideoTitle);

					const downloadFinalVideoBtn = document.createElement("button");
					downloadFinalVideoBtn.className = "download-btn";
					downloadFinalVideoBtn.innerHTML =
						'<span class="download-icon">⬇️</span> Download';
					downloadFinalVideoBtn.addEventListener("click", function () {
						const finalVideoElement =
							finalVideoContainer.querySelector("video");
						if (finalVideoElement && finalVideoElement.src) {
							downloadVideo(finalVideoElement.src, "hongos_final_video.mp4");
						} else {
							console.error("Final video source not found");
						}
					});

					finalVideoHeader.appendChild(downloadFinalVideoBtn);
					finalVideoContainer.appendChild(finalVideoHeader);

					const finalVideo = document.createElement("video");
					finalVideo.controls = true;
					// Add timestamp to prevent caching
					finalVideo.src =
						"/" + result.final_video_path + "?t=" + new Date().getTime();
					console.log(`Setting final video src to: ${finalVideo.src}`);
					finalVideoContainer.appendChild(finalVideo);

					resultElement.appendChild(finalVideoContainer);
				}

				// Add to results container
				resultsContainer.appendChild(resultElement);
			}
		});

		// Hide placeholder when results are available
		const resultsPlaceholder = document.getElementById("resultsPlaceholder");
		if (resultsPlaceholder && results.some((r) => r.status === "completed")) {
			resultsPlaceholder.style.display = "none";
		}
	}

	// Helper function to update a single result without clearing the entire container
	function updateSingleResult(result) {
		console.log(`Updating single result #${result.id} with final video`);

		// Find the existing result element
		const resultElement = document.querySelector(
			`.result-item[data-id="${result.id}"]`
		);
		if (!resultElement) {
			console.error(`Could not find result element for ID ${result.id}`);
			return;
		}

		// Check if final video container already exists
		let finalVideoContainer = document.getElementById(
			`final-video-container-${result.id}`
		);
		if (finalVideoContainer) {
			console.log(`Final video container already exists for ID ${result.id}`);
			return;
		}

		// Create and add the final video container
		finalVideoContainer = document.createElement("div");
		finalVideoContainer.className = "video-container";
		finalVideoContainer.id = `final-video-container-${result.id}`;

		const finalVideoHeader = document.createElement("div");
		finalVideoHeader.className = "video-header";

		const finalVideoTitle = document.createElement("h3");
		finalVideoTitle.textContent = "Final Video";
		finalVideoHeader.appendChild(finalVideoTitle);

		const downloadFinalVideoBtn = document.createElement("button");
		downloadFinalVideoBtn.className = "download-btn";
		downloadFinalVideoBtn.innerHTML =
			'<span class="download-icon">⬇️</span> Download';
		downloadFinalVideoBtn.addEventListener("click", function () {
			const finalVideoElement = finalVideoContainer.querySelector("video");
			if (finalVideoElement && finalVideoElement.src) {
				downloadVideo(finalVideoElement.src, "hongos_final_video.mp4");
			} else {
				console.error("Final video source not found");
			}
		});

		finalVideoHeader.appendChild(downloadFinalVideoBtn);
		finalVideoContainer.appendChild(finalVideoHeader);

		const finalVideo = document.createElement("video");
		finalVideo.controls = true;
		finalVideo.src =
			"/" + result.final_video_path + "?t=" + new Date().getTime();
		console.log(`Setting final video src to: ${finalVideo.src}`);
		finalVideoContainer.appendChild(finalVideo);

		resultElement.appendChild(finalVideoContainer);

		// Hide the process button if it exists
		const processBtn = resultElement.querySelector(".process-btn");
		if (processBtn) {
			processBtn.style.display = "none";
		}

		// Hide the processing status if it exists
		const statusElement = document.getElementById(
			`processing-status-${result.id}`
		);
		if (statusElement) {
			statusElement.style.display = "none";
		}
	}

	async function processFolder(id) {
		console.log(`Starting to process folder for generation ID: ${id}`);

		// Disable the button
		const processBtn = document.querySelector(
			`.result-item[data-id="${id}"] .process-btn`
		);
		if (processBtn) {
			processBtn.disabled = true;
			processBtn.textContent = "Processing...";
		}

		// Show processing status
		const statusElement = document.getElementById(`processing-status-${id}`);
		if (statusElement) {
			statusElement.textContent = "Generating Video...";
			statusElement.className = "processing-status running with-spinner";
		}

		try {
			// Get the currently selected video model
			const videoModel = document.getElementById("videoModel").value;
			console.log(`Using video model for processing: ${videoModel}`);

			// Call the API to process the folder with the selected model
			console.log(
				`Calling /process-folder/${id} API with model: ${videoModel}`
			);
			const response = await fetch(`/process-folder/${id}`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({
					video_model: videoModel,
				}),
			});

			if (!response.ok) {
				throw new Error(`Server error: ${response.status}`);
			}

			console.log(
				`Process folder API call successful, starting status check interval`
			);

			// Start checking status
			const processingCheckInterval = setInterval(async () => {
				try {
					const statusResponse = await fetch("/status");
					const results = await statusResponse.json();
					console.log(`Status check results:`, results);

					// Find our current generation
					const result = results.find((r) => r.id === id);
					console.log(`Current result for ID ${id}:`, result);

					if (!result) {
						clearInterval(processingCheckInterval);
						if (statusElement) {
							statusElement.textContent = "Error: Result not found";
							statusElement.className = "processing-status error";
						}
						return;
					}

					// Check processing status
					if (result.processing_status === "completed") {
						clearInterval(processingCheckInterval);
						console.log(
							`Processing completed for ID ${id}, final_video_path:`,
							result.final_video_path
						);

						// Update the UI with the new results
						updateResults(results);

						// Create the final video container if it doesn't exist
						const resultElement = document.querySelector(
							`.result-item[data-id="${id}"]`
						);
						if (resultElement) {
							console.log(`Found result element for ID ${id}`);

							// Check if final video container already exists
							let finalVideoContainer = document.getElementById(
								`final-video-container-${id}`
							);

							if (!finalVideoContainer && result.final_video_path) {
								console.log(`Creating new final video container for ID ${id}`);

								// Create final video container
								finalVideoContainer = document.createElement("div");
								finalVideoContainer.className = "video-container";
								finalVideoContainer.id = `final-video-container-${id}`;

								const finalVideoHeader = document.createElement("div");
								finalVideoHeader.className = "video-header";

								const finalVideoTitle = document.createElement("h3");
								finalVideoTitle.textContent = "Final Video";
								finalVideoHeader.appendChild(finalVideoTitle);

								const downloadFinalVideoBtn = document.createElement("button");
								downloadFinalVideoBtn.className = "download-btn";
								downloadFinalVideoBtn.innerHTML =
									'<span class="download-icon">⬇️</span> Download';
								downloadFinalVideoBtn.addEventListener("click", function () {
									const finalVideoElement =
										finalVideoContainer.querySelector("video");
									if (finalVideoElement && finalVideoElement.src) {
										downloadVideo(
											finalVideoElement.src,
											"hongos_final_video.mp4"
										);
									} else {
										console.error("Final video source not found");
									}
								});

								finalVideoHeader.appendChild(downloadFinalVideoBtn);
								finalVideoContainer.appendChild(finalVideoHeader);

								const finalVideo = document.createElement("video");
								finalVideo.controls = true;
								// Add a timestamp to prevent caching
								finalVideo.src = `/${
									result.final_video_path
								}?t=${new Date().getTime()}`;
								console.log(`Setting final video src to: ${finalVideo.src}`);
								finalVideoContainer.appendChild(finalVideo);

								// Add to result element
								resultElement.appendChild(finalVideoContainer);

								// Hide the process button and status
								const processBtn = resultElement.querySelector(".process-btn");
								if (processBtn) {
									processBtn.style.display = "none";
								}

								if (statusElement) {
									statusElement.style.display = "none";
								}

								// Scroll to the final video
								finalVideoContainer.scrollIntoView({
									behavior: "smooth",
									block: "nearest",
								});
							} else if (finalVideoContainer) {
								console.log(
									`Final video container already exists for ID ${id}`
								);
							} else {
								console.error(
									`No final_video_path found in result for ID ${id}`
								);
							}
						} else {
							console.error(`Could not find result element for ID ${id}`);
						}
					} else if (result.processing_status === "error") {
						clearInterval(processingCheckInterval);
						console.error(
							`Processing error for ID ${id}:`,
							result.processing_error
						);
						if (statusElement) {
							statusElement.textContent = `Error: ${
								result.processing_error || "Unknown error"
							}`;
							statusElement.className = "processing-status error";
						}
						if (processBtn) {
							processBtn.disabled = false;
							processBtn.textContent = "Try Again";
						}
					} else {
						console.log(
							`Processing status for ID ${id}: ${
								result.processing_status || "running"
							}`
						);
					}
				} catch (error) {
					console.error("Error checking processing status:", error);
				}
			}, 2000);
		} catch (error) {
			console.error(`Error processing folder for ID ${id}:`, error);
			if (statusElement) {
				statusElement.textContent = `Error: ${error.message}`;
				statusElement.className = "processing-status error";
			}
			if (processBtn) {
				processBtn.disabled = false;
				processBtn.textContent = "Try Again";
			}
		}
	}

	function showError(message) {
		statusContainer.classList.add("hidden");
		errorContainer.classList.remove("hidden");
		errorText.textContent = message;
	}

	// Initial check for existing results
	fetch("/status")
		.then((response) => response.json())
		.then((results) => {
			if (results.length > 0) {
				updateResults(results);
			}
		})
		.catch((error) => {
			console.error("Error loading initial results:", error);
		});

	// Toggle config panel
	configBtn.addEventListener("click", function () {
		configPanel.classList.toggle("visible");
		configBtn.classList.toggle("active");
	});

	// Save API keys
	saveGeminiKeyBtn.addEventListener("click", async function () {
		await saveApiKey("gemini", geminiApiKeyInput.value.trim());
	});

	saveFalKeyBtn.addEventListener("click", async function () {
		await saveApiKey("fal", falApiKeyInput.value.trim());
	});

	saveElevenLabsKeyBtn.addEventListener("click", async function () {
		await saveApiKey("elevenlabs", elevenLabsApiKeyInput.value.trim());
	});

	async function saveApiKey(keyType, apiKey) {
		if (!apiKey) return;

		try {
			const response = await fetch("/set-api-key", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({
					key_type: keyType,
					api_key: apiKey,
				}),
			});

			if (response.ok) {
				alert(
					`${
						keyType.charAt(0).toUpperCase() + keyType.slice(1)
					} API key saved successfully!`
				);
			} else {
				alert("Failed to save API key");
			}
		} catch (error) {
			alert("Error: " + error.message);
		}
	}

	// Check if API keys are set and load current values
	async function checkApiKeys() {
		try {
			const response = await fetch("/api-keys-status");
			const data = await response.json();

			// Set input values to masked versions of the keys
			if (data.gemini_key) {
				geminiApiKeyInput.value = maskApiKey(data.gemini_key);
				geminiApiKeyInput.setAttribute("data-has-value", "true");
			}

			if (data.fal_key) {
				falApiKeyInput.value = maskApiKey(data.fal_key);
				falApiKeyInput.setAttribute("data-has-value", "true");
			}

			if (data.elevenlabs_key) {
				elevenLabsApiKeyInput.value = maskApiKey(data.elevenlabs_key);
				elevenLabsApiKeyInput.setAttribute("data-has-value", "true");
			}

			// Show config panel if any key is missing
			if (
				!data.gemini_key_set ||
				!data.fal_key_set ||
				!data.elevenlabs_key_set
			) {
				configPanel.classList.add("visible");
				configBtn.classList.add("active");
			}
		} catch (error) {
			console.error("Error checking API keys:", error);
		}
	}

	// Helper function to mask API keys
	function maskApiKey(key) {
		if (!key) return "";
		if (key.length <= 8) return "••••••••";
		return key.substring(0, 4) + "••••••••" + key.substring(key.length - 4);
	}

	// Add focus event to clear masked values
	[geminiApiKeyInput, falApiKeyInput, elevenLabsApiKeyInput].forEach(
		(input) => {
			input.addEventListener("focus", function () {
				if (this.getAttribute("data-has-value") === "true") {
					this.value = "";
				}
			});
		}
	);

	// Call this at the end of the DOMContentLoaded event handler
	checkApiKeys();

	// Handle background music volume slider
	const volumeSlider = document.getElementById("backgroundMusicVolume");
	const volumeValue = document.getElementById("volumeValue");

	if (volumeSlider && volumeValue) {
		volumeSlider.addEventListener("input", function () {
			volumeValue.textContent = this.value + "%";
		});
	}

	// Image upload handling
	document
		.querySelector(".file-input-button")
		.addEventListener("click", function () {
			document.getElementById("imageUpload").click();
		});

	document
		.getElementById("imageUpload")
		.addEventListener("change", async function (event) {
			const file = event.target.files[0];
			if (!file) return;

			// Update the file name display
			document.querySelector(".file-name").textContent = file.name;

			// Create a FormData object
			const formData = new FormData();
			formData.append("file", file);

			try {
				// Show loading state
				document.querySelector(".file-name").textContent = "Uploading...";

				// Upload the file
				const response = await fetch("/upload-image", {
					method: "POST",
					body: formData,
				});

				if (!response.ok) {
					throw new Error("Upload failed");
				}

				const data = await response.json();

				// Store the upload ID
				document.getElementById("initialImageId").value = data.upload_id;

				// Show the preview
				const previewImage = document.getElementById("previewImage");
				previewImage.src = URL.createObjectURL(file);
				document.querySelector(".file-name").textContent = file.name;

				// Make sure the preview container is visible
				const uploadPreview = document.getElementById("uploadPreview");
				uploadPreview.classList.remove("hidden");
			} catch (error) {
				console.error("Error uploading image:", error);
				document.querySelector(".file-name").textContent =
					"Upload failed. Try again.";
				setTimeout(() => {
					document.querySelector(".file-name").textContent = "No file chosen";
				}, 3000);
			}
		});

	// Clear image button
	document
		.getElementById("clearImageBtn")
		.addEventListener("click", async function () {
			const uploadId = document.getElementById("initialImageId").value;
			if (!uploadId) return;

			try {
				// Clear the image on the server
				await fetch(`/clear-image/${uploadId}`, {
					method: "POST",
				});

				// Reset the UI
				document.getElementById("initialImageId").value = "";
				document.getElementById("imageUpload").value = "";
				document.querySelector(".file-name").textContent = "No file chosen";

				// Hide the preview
				document.getElementById("uploadPreview").classList.add("hidden");
			} catch (error) {
				console.error("Error clearing image:", error);
			}
		});

	// Add this to your existing JavaScript to toggle the visibility of the video model dropdown
	document
		.getElementById("generateVideos")
		.addEventListener("change", function () {
			const videoModelContainer = document.getElementById(
				"videoModelContainer"
			);
			if (this.checked) {
				videoModelContainer.style.display = "block";
			} else {
				videoModelContainer.style.display = "none";
			}
		});

	// Initialize the visibility on page load
	document.addEventListener("DOMContentLoaded", function () {
		const generateVideos = document.getElementById("generateVideos");
		const videoModelContainer = document.getElementById("videoModelContainer");

		if (generateVideos.checked) {
			videoModelContainer.style.display = "block";
		} else {
			videoModelContainer.style.display = "none";
		}
	});

	// Function to update the UI with generation results
	function updateUIWithResults(data) {
		console.log("Updating UI with results:", data);

		// Hide the loading indicator
		document.getElementById("loadingIndicator").style.display = "none";

		// Show the results container
		const resultsContainer = document.getElementById("resultsContainer");
		resultsContainer.style.display = "block";

		// Update the slideshow video if available
		if (data.video_path) {
			const videoPath = data.video_path.replace(/^.*[\\\/]/, "");
			const videoContainer = document.getElementById("videoContainer");
			const videoElement = document.getElementById("generatedVideo");

			// Set the video source with a timestamp to prevent caching
			videoElement.src = `outputs/${data.output_dir
				.split("/")
				.pop()}/${videoPath}?t=${new Date().getTime()}`;
			videoContainer.style.display = "block";

			console.log("Updated slideshow video source:", videoElement.src);

			// Show the "Generate Full Video" button if it's not already generated
			if (!data.final_video_path) {
				document.getElementById("generateFullVideoBtn").style.display = "block";
			}
		}

		// Update the full video if available
		if (data.final_video_path) {
			const finalVideoPath = data.final_video_path.replace(/^.*[\\\/]/, "");
			const finalVideoContainer = document.getElementById(
				"finalVideoContainer"
			);
			const finalVideoElement = document.getElementById("finalVideo");

			// Set the video source with a timestamp to prevent caching
			finalVideoElement.src = `outputs/${data.output_dir
				.split("/")
				.pop()}/${finalVideoPath}?t=${new Date().getTime()}`;
			finalVideoContainer.style.display = "block";

			console.log("Updated final video source:", finalVideoElement.src);

			// Hide the "Generate Full Video" button since we now have the full video
			document.getElementById("generateFullVideoBtn").style.display = "none";
		}

		// Store the output directory for later use
		currentOutputDir = data.output_dir;
	}

	// Check if the generate full video button exists
	if (!document.getElementById("generateFullVideoBtn")) {
		// Create the button if it doesn't exist
		const generateBtn = document.createElement("button");
		generateBtn.id = "generateFullVideoBtn";
		generateBtn.className = "btn btn-primary";
		generateBtn.textContent = "Generate Full Video";
		generateBtn.style.display = "none";

		// Find a good place to insert it (after the video container)
		const videoContainer = document.getElementById("videoContainer");
		if (videoContainer) {
			videoContainer.insertAdjacentElement("afterend", generateBtn);
		} else {
			// If video container doesn't exist, add it to the results container
			const resultsContainer = document.getElementById("resultsContainer");
			if (resultsContainer) {
				resultsContainer.appendChild(generateBtn);
			}
		}
	}

	// Now add the event listener, but only if the element exists
	const generateFullVideoBtn = document.getElementById("generateFullVideoBtn");
	if (generateFullVideoBtn) {
		generateFullVideoBtn.addEventListener("click", function () {
			// Your existing code for the button click event
			if (!currentOutputDir) {
				alert("No generation results available");
				return;
			}

			// Show loading indicator
			document.getElementById("loadingIndicator").style.display = "block";

			// Call the API to generate the full video
			fetch("/generate_full_video", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({ output_dir: currentOutputDir }),
			})
				.then((response) => response.json())
				.then((data) => {
					// Hide loading indicator
					document.getElementById("loadingIndicator").style.display = "none";

					if (data.error) {
						alert("Error generating full video: " + data.error);
						return;
					}

					// Update the UI with the new full video
					if (data.final_video_path) {
						const finalVideoPath = data.final_video_path.replace(
							/^.*[\\\/]/,
							""
						);
						const finalVideoContainer = document.getElementById(
							"finalVideoContainer"
						);
						const finalVideoElement = document.getElementById("finalVideo");

						// Set the video source with a timestamp to prevent caching
						finalVideoElement.src = `outputs/${data.output_dir
							.split("/")
							.pop()}/${finalVideoPath}?t=${new Date().getTime()}`;
						finalVideoContainer.style.display = "block";

						console.log("Updated final video source:", finalVideoElement.src);

						// Hide the button
						document.getElementById("generateFullVideoBtn").style.display =
							"none";
					}
				})
				.catch((error) => {
					console.error("Error:", error);
					document.getElementById("loadingIndicator").style.display = "none";
					alert("Error generating full video: " + error);
				});
		});
	} else {
		console.warn("Generate Full Video button not found in the DOM");
	}

	// Function to handle video downloads
	function downloadVideo(videoUrl, filename) {
		// Create a temporary anchor element
		const a = document.createElement("a");
		a.href = videoUrl;
		a.download = filename || "video.mp4";
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
	}

	// Add download button functionality for the slideshow video
	function setupVideoDownloads() {
		// For the final video
		const downloadFinalVideoBtn = document.getElementById("downloadFinalVideo");
		if (downloadFinalVideoBtn) {
			downloadFinalVideoBtn.addEventListener("click", function () {
				const finalVideo = document.getElementById("finalVideo");
				if (finalVideo && finalVideo.src) {
					downloadVideo(finalVideo.src, "hongos_final_video.mp4");
				} else {
					console.error("Final video source not found");
				}
			});
		}
	}

	// Call this function when the DOM is loaded
	document.addEventListener("DOMContentLoaded", function () {
		// ... your existing code ...

		setupVideoDownloads();
	});
});
